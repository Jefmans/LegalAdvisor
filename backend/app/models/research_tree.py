# app/models/research_tree.py
from __future__ import annotations
from typing import List, Optional, Set
from pydantic import BaseModel, Field
from uuid import uuid4, UUID

class Chunk(BaseModel):
    id: str
    text: str
    page: Optional[int]
    source: Optional[str]
    embedding: Optional[List[float]] = None

class ResearchNode(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    goals: Optional[str] = None
    questions: List[str] = Field(default_factory=list)
    chunks: List[Chunk] = Field(default_factory=list)
    chunk_ids: Set[str] = Field(default_factory=set)
    content: Optional[str] = None
    summary: Optional[str] = None
    conclusion: Optional[str] = None
    is_final: bool = False
    parent: Optional["ResearchNode"] = None
    subnodes: List["ResearchNode"] = Field(default_factory=list)
    rank: Optional[int] = 0
    level: Optional[int] = 0

    def __str__(self): return f"{self.title} : rank {self.rank} - level {self.level}"

    @property
    def display_rank(self) -> str:
        # root -> show its own rank (usually 1), no prefix
        if self.parent is None:
            return str(self.rank or 1)
        # top-level children -> don't include the root's "1" in the prefix
        if self.parent.parent is None:
            return str(self.rank or 1)
        # deeper levels -> include parent's display rank
        return f"{self.parent.display_rank}.{self.rank or 1}"
    

    @property
    def parent_title(self) -> Optional[str]:
        return self.parent.title if self.parent else None

    def add_subnode(self, node: "ResearchNode"):
        node.parent = self
        node.level = (self.level or 0) + 1
        node.rank  = len(self.subnodes) + 1
        self.subnodes.append(node)

    def walk(self) -> List["ResearchNode"]:
        nodes = [self]
        for sub in self.subnodes: nodes.extend(sub.walk())
        return nodes

    def mark_final(self): self.is_final = True

    # ---- factory from ORM row (kept tiny; repo hydrates collections) ----
    @classmethod
    def from_orm_model(cls, orm_node) -> "ResearchNode":
        return cls(
            id=orm_node.id, title=orm_node.title, goals=orm_node.goals,
            content=orm_node.content, summary=orm_node.summary,
            conclusion=orm_node.conclusion, rank=orm_node.rank,
            level=orm_node.level, is_final=orm_node.is_final,
            questions=[], chunks=[], chunk_ids=set(), subnodes=[]
        )

    class Config: arbitrary_types_allowed = True

class ResearchTree(BaseModel):
    query: str
    root_node: ResearchNode
    used_questions: Set[str] = Field(default_factory=set)
    used_chunk_ids: Set[str] = Field(default_factory=set)

    class Config: arbitrary_types_allowed = True

    def assign_rank_and_level(self):
        def _recurse(node: ResearchNode, parent: Optional[ResearchNode], level: int):
            node.parent = parent
            node.level = level
            for i, child in enumerate(node.subnodes, start=1):
                child.rank = i
                _recurse(child, node, level + 1)
        self.root_node.parent = None
        self.root_node.rank = 1
        self.root_node.level = 1
        _recurse(self.root_node, None, 1)

    def all_nodes(self) -> List[ResearchNode]:
        out: List[ResearchNode] = []
        def walk(n: ResearchNode):
            out.append(n)
            for s in n.subnodes: walk(s)
        walk(self.root_node)
        return out

    def model_dump_jsonable(self):
        def clean_node(node):
            return {
                "title": node.title,
                "rank": node.rank,
                "level": node.level,
                "parent_rank": node.parent.rank if node.parent else None,
                "parent_level": node.parent.level if node.parent else None,
                "display_rank": node.display_rank,
                "questions": node.questions,
                "chunks": [c.dict() for c in node.chunks],
                "chunk_ids": list(node.chunk_ids),
                "content": node.content,
                "summary": node.summary,
                "conclusion": node.conclusion,
                "is_final": node.is_final,
                "subnodes": [clean_node(sn) for sn in node.subnodes],
            }
        return {
            "query": self.query,
            "root_node": clean_node(self.root_node),
            "used_questions": list(self.used_questions),
            "used_chunk_ids": list(self.used_chunk_ids),
        }
