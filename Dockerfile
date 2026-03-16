FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Bratislava


RUN apt-get update && apt-get install -y \
    tzdata \
    apache2 \
    php \
    libapache2-mod-php \
    php-cli \
    python3.12 \
    python3.12-venv \
    python3-pip \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*


RUN python3.12 -m venv /opt/venv && \
    chown -R www-data:www-data /opt/venv
 
ENV PATH="/opt/venv/bin:$PATH"
 
COPY requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install -r /tmp/requirements.txt

COPY php.ini /etc/php/8.3/apache2/php.ini

RUN a2enmod rewrite

RUN sed -i 's|/var/www/html|/var/www/app|g' /etc/apache2/sites-available/000-default.conf

RUN echo '<Directory /var/www/app>\n\
    Options Indexes FollowSymLinks\n\
    AllowOverride All\n\
    Require all granted\n\
</Directory>' >> /etc/apache2/apache2.conf


COPY app/       /var/www/app/
COPY scripts/   /var/www/scripts/
COPY config.py  /var/www/config.py
COPY config.php /var/www/config.php

RUN mkdir -p /var/www/app/storage && \
    chown -R www-data:www-data /var/www/app/storage && \
    chown -R www-data:www-data /var/www/scripts && \
    chown -R www-data:www-data /var/www/config.py && \
    chown -R www-data:www-data /var/www/config.php && \
    chmod -R 755 /var/www/app/storage

EXPOSE 80

CMD ["apachectl", "-D", "FOREGROUND"]
