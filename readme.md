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
Installation instructions are for Ubuntu 14.04 (on Cloud9):

## CONFIGURE POSTGRESQL
Configuring Postgres 9.3 which is already installed on Cloud9:  
$ sudo service postgresql start  
$ sudo sudo -u postgres psql  
postgres=# \password postgres  
Enter new password:   
Enter it again:   
postgres=# \q  
$ sudo sudo -u postgres createuser jrc -P -s  
Enter password for new role:  
Enter it again:  

## CONFIGURE PHPPGADMIN
$ sudo cp /etc/apache2/conf.d/phppgadmin /etc/apache2/conf-enabled/phppgadmin.conf  
$ sudo /etc/init.d/apache2 restart  
$ sudo nano /etc/apache2/conf-enabled/phppgadmin.conf  
Edit to ‘allow from all’  
$ sudo service apache2 reload  
Available here: [https://&lt;c9workspacename&gt;-&lt;c9username&gt;.c9users.io/phppgadmin/](https://<c9workspacename>-<c9username>.c9users.io/phppgadmin/)

## INSTALL POSTGIS
$ sudo apt-get update  
$ sudo apt-get install postgresql postgresql-contrib postgis postgresql-9.3-postgis-scripts  
$ sudo apt-get update  
In phppgadmin, run the sql script 'scripts/setup_postgis.sql'  

## PYTHON REST SERVER
- Clone the GitHub repo in Cloud9 to create a new workspace  
- In phppgadmin, create a database in phpPgAdmin with UTF-8 encoding  
- In phppgadmin, run the sql script 'scripts/database_objects.sql' to create the necessary database objects in Postgresql  
- Copy the resources_empty.py file and rename to resources.py and create the database connection strings.   

## PYTHON PREREQUISITES
$ sudo easy_install flup==1.0.3.dev-20110405   
$ sudo easy_install psycopg2  
$ sudo easy_install pdfkit  
$ sudo easy_install lxml  
$ sudo easy_install web.py  

## CONFIGURE APACHE
Apache must be configured to run CGI scripts:  
$ sudo a2enmod cgi  
$ sudo vi /etc/apache2/conf-available/serve-cgi-bin.conf  
In the IfDefine section of the file, enter the following:  
&nbsp;&nbsp;&nbsp;&nbsp;ScriptAlias /cgi-bin/ /home/ubuntu/workspace/cgi-bin/  
&nbsp;&nbsp;&nbsp;&nbsp;&lt;Directory "/home/ubuntu/workspace/cgi-bin"&gt;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;AllowOverride None  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Options +ExecCGI -MultiViews +SymLinksIfOwnerMatch  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;AddHandler cgi-script .cgi .py  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Require all granted  
&nbsp;&nbsp;&nbsp;&nbsp;&lt;/Directory&gt;  
Start Apache  
Available here: [https://&lt;c9workspacename&gt;-&lt;c9username&gt;.c9users.io/cgi-bin/services.py/](https://<c9workspacename>-<c9username>.c9users.io/cgi-bin/services.py/)
