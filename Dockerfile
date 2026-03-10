FROM ubuntu:24.04
RUN apt-get -y update
RUN apt -y install apache2
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Bratislava
RUN apt-get install -y tzdata
RUN rm /var/www/html/index.html
RUN apt-get update
#RUN apt install -y install curl unzip
#RUN apt install php php-cli php-curl php-mbstring php-common php-dev unzip -y
#RUN sed -i 's/upload_max_filesize = 2M/upload_max_filesize = 50M/g' /etc/php/7.4/apache2/php.ini
#RUN sed -i 's/post_max_size = 8M/post_max_size = 2048M/g' /etc/php/7.4/apache2/php.ini
#RUN sed -i 's/max_file_uploads = 8M/max_file_uploads = 2000/g' /etc/php/7.4/apache2/php.ini
#RUN sed -i 's/max_execution_time = 30/max_execution_time = 0/g' /etc/php/7.4/apache2/php.ini
#RUN sed -i 's/memory_limit = 2048M/memory_limit = 2048M/g' /etc/php/7.4/apache2/php.ini

RUN add-apt-repository ppa:savoury1/python
RUN apt update -y
RUN apt-get install python3.12
RUN apt-get install python3.12-venv
RUN apt-get install python3.12-venv

#RUN apt-get -y update
#RUN apt-get -y install software-properties-common
#RUN apt-get -y update
#RUN apt -y install python3.10
#RUN apt -y install python3-pip

# next steps:
# docker build -t web_image .
# docker run -dit -v path.to.html:/var/www/html/ -v path.to.code:/home/code/ -- name trading_web -p 8080:80 web_image

