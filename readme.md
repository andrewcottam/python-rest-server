Python 3.6 implementation using Tornado  
# Installation  
## Install PostGIS
## Clone this repo  
```
git clone https://github.com/andrewcottam/python-rest-server.git
```
## Create the database and database objects  
```
sudo -u postgres psql -f <path>/python-rest-server/scripts/database_objects.sql 
```
## Start the server
This starts the server listening on port 8081:  
```
python <path>/python-rest-server/services.py 8081  
```
## Navigate to the server services directory
http://localhost:8081/python-rest-server/
## Test a service
Navigate to the pythonrestserver database, test schema, get_species service and click the first example call

# Documentation
Documentation on how to create and consume REST services is given in the Help link of the server services directory
