When starting new server:
1) root into your server with ssh
2) git clone
3) install docker https://docs.docker.com/engine/install/ubuntu/ + "apt install docker-compose" (https://docs.docker.com/compose/install/linux/#install-using-the-repository)
4) create .env
5) docker-compose up -d



When new start dockers:
1) create ES views in Kibana => "pdf_chunks" - "captions"  (http://65.109.170.93/kibana/app/management/data/index_management/indices)
2) create buckets in MiniO => "images" - "uploads"








TO DO 
-----

1) Save metadata list from images => PostgreSQL
        a. is in process in the backend


2) langchain-elasticsearch==0.1.3 => langchain-elasticsearch==0.3.2 + elasticsearch==9.x
        a. change embedding field name ??


3) it is possible to upload the same file twice

4) Update Embedding Upload in Elastic to add "metadata = {}" => to be able to access other fiels like "pages, ..."

5) create CONSTANTS for all the system ... + us .env

6) secure the system (Elastic, ...) with pw + vault + ...

7) use Tailscale

8) storing in Elastic => we're using different methods in different places for "pdf_chunks" - "captions" => streamline

9) USE CLIP to generate text based on image




DON'T FORGET
--------------
1)  metadata route in backend use the  metadata route in pdf_worker => And then saves this data to postgress 