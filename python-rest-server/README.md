python-rest-server
==================

Apache Server extension to publish and document Postgresql resources as REST Web Services in an HTML Services Directory.
The REST Services Directory makes available in HTML format, functions from a Postgresql database. It supports the following features to expose your data as a REST service:

* Automatically creates HTML pages from schemas and functions in a Postgresql database
* Publishes the descriptions as HTML for functions and function parameters based on COMMENTS in the database
* Creates a service page for each function in a postgresql schema including information on the parameters, descriptions, types and default values
* Creates sample REST service calls for each service

To take advantage of these features you simply need to create a function in Postgresql with a description. Optionally you can add additional information to the function such as parameter descriptions.

# Installation
Installation instructions for Ubuntu 12.04 LTS:

## INSTALL AND CONFIGURE POSTGRESQL 9.1
1.	Install Postgresql 9.1
2.	Create a password for the postgres user to be able to access the server  
3.	(optional) Create a user for the unix user so you don’t have to run psql as sudo (-P to enter password –s – superuser): 
sudo -u postgres createuser jrc -P -s
4.	Create a new database:
createdb -O jrc sprep_ris
5.	Allow access to Postgresql for local network users (see here) using the internal IP address by editing the pg_hba.conf file:
sudo nano ~/../../etc/postgresql/9.1/main/pg_hba.conf
host    all             all             172.20.20.6/32             md5
5.	Enable PostgreSQL to listen across different networks:
sudo nano ~/../../etc/postgresql/9.1/main/postgresql.conf
listen_addresses = '*'
6.	Reload the configuration files and restart the server:
sudo /etc/init.d/postgresql reload 
sudo /etc/init.d/postgresql restart
7.	Configure postgresql for access from pgAdmin
sudo apt-get install pgadmin3
sudo apt-get install postgresql-contrib
sudo -u postgres psql
CREATE EXTENSION adminpack;
8.	Connect from pgAdmin using ssh tunnelling (see Using Putty)
9.	Run the sql script database_objects.sql to create the necessary database objects in Postgresql

## INSTALL PYTHON REST SERVER
1.	Install Git:
sudo apt-get install git
2.	Install setuptools:
sudo apt-get install python-setuptools
3.	Install Pip:
wget https://bootstrap.pypa.io/get-pip.py
sudo python get-pip.py
4.	Install flup:
wget http://www.saddi.com/software/flup/dist/flup-1.0.2.tar.gz
tar -xvzf flup-1.0.2.tar.gz
cd flup-1.0.2/
sudo python setup.py install
5.	Install webpy:
wget http://webpy.org/static/web.py-0.37.tar.gz
tar -xvzf web.py-0.37.tar.gz
cd web.py-0.37/
sudo python setup.py install
6.	Install psycopg2:
sudo apt-get install python-psycopg2 
7.	Install pdfkit:
sudo pip install pdfkit
sudo apt-get install wkhtmltopdf
sudo apt-get install libicu48
Follow instructions here to create a virtual X server:
sudo apt-get install xvfb
sudo nano ../../usr/bin/wkhtmltopdf.sh
Paste in:
#!/bin/bash
xvfb-run --server-args="-screen 0, 1024x768x24" /usr/bin/wkhtmltopdf $*
Then:
sudo chmod a+x ~/../../usr/bin/wkhtmltopdf.sh
sudo ln -s ~/../../usr/bin/wkhtmltopdf.sh ~/../../usr/local/bin/wkhtmltopdf
8.	Install OrderedDict:
wget https://pypi.python.org/packages/source/o/ordereddict/ordereddict-1.1.tar.gz
tar -xvzf ordereddict-1.1.tar.gz
cd ordereddict-1.1/
sudo python setup.py install
9.	Install lxml:
sudo apt-get install libxml2-dev libxslt-dev python-dev
sudo apt-get install lib32z1-dev
wget https://pypi.python.org/packages/source/l/lxml/lxml-3.4.3.tar.gz
tar -xvzf lxml-3.4.3.tar.gz
cd lxml-3.4.3/
sudo python setup.py install
10.	Change to web root on Apache
cd ~/../../var/www/
11.	Clone the repo
sudo git clone https://github.com/andrewcottam/python-rest-server.git
12.	rename the ‘/var/www/python-rest-server/cgi-bin/resources_empty.py’ to ‘resources.py’
sudo mv python-rest-server/cgi-bin/resources_empty.py python-rest-server/cgi-bin/resources.py
13.	Add database connection strings and descriptions in the dbconnect.py file
databases = {
    "default": dict(connectionString="dbname='sprep_ris' host='172.20.20.6' user='jrc' password='<whatever>'", description="<Description that will appear in the services directory>")
}
14.	Add schemas and functions so they can be tested

## CONFIGURE APACHE WEB SERVER
1.	Enable CGI processing in Apache:
sudo a2enmod cgi
2.	Add a ScriptAlias in the vhost file to point to the /python-rest-server/cgi-bin folder, e.g. add the following to the ‘etc/apache2/sites-available/default’ file (in Ubuntu 10.0.4):
ScriptAlias /rest /var/www/python-rest-server/cgi-bin/services
3.	Add a DocumentRoot in the vhost file to point to the /python-rest-server/htmldocs folder, e.g. Add the following to the ‘etc/apache2/sites-available/default’ file (in Ubuntu 10.0.4):
DocumentRoot /var/www/python-rest-server/htmldocs
If you already have a DocumentRoot defined and you are not using separate domains in the Apache vhost.conf files, then you can move the /python-rest-server/htmldocs folder to the existing DocumentRoot:
sudo cp /var/www/python-rest-server/htmldocs/ /var/www/resthtmldocs/ -r
sudo rm /var/www/python-rest-server/htmldocs/ -r
and set the relative path in the /cgi-bin/resources.py file:
documentRoot = “/resthtmldocs”
This will make sure that all of the html files are found when deployed.
4.	Restart Apache (sudo service apache2 restart)

## On Cloud9, the setup is a bit different:
This is nearly complete, but might be a few issues.

### TO SET UP POSTGREQL
* sudo service postgresql start
* root@blishten-python-4336349:/home/ubuntu/workspace# sudo -u postgres createuser jrc -P -s
* Enter password for new role: jrc
* Enter it again: jrc
* root@blishten-python-4336349:/home/ubuntu/workspace# sudo -u postgres createdb -O jrc sprep_ris
* blishten:~/workspace (master) $ psql -d sprep_ris -a -f "python-rest-server/cgi-bin/database_objects.sql"

### TO SETUP APACHE
* Following the guide here: https://community.c9.io/t/running-a-python-cgi-server/1602
* In the vi editor, type INSERT to go into insert mode and edit the text to something like ‘/home/ubuntu/workspace/python-rest-server/cgi-bin’ and then type ESC then : then x then RETURN
* chmod +x -R /home/ubuntu/workspace/python-rest-server/cgi-bin

### INSTALL PYTHON REST SERVER
differences to above are:
* 6. sudo easy_install psycopg2
* 7. sudo easy_install pdfkit
* 9. sudo easy_install lxml

### TO CHANGE THE SU PASSWORD ON UBUNTU:
* sudo su
* passwd ubuntu
* normal password
* You will now be logged in as root
* GOTO:
*  https://python-blishten.c9users.io/python-rest-server/cgi-bin/services.py/
