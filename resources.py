# Python module that stores site specific information for database connections, user accounts and file/folder paths
import sys
import psycopg2, psycopg2.extras

databases = {
    "pythonrestserver": dict(connectionString="dbname='pythonrestserver' host='localhost' user='jrc' password='thargal88'", description="Python REST Server Database")
}

#set the documentRoot to the relative path to the python-rest-server/htmldocs folder from the Apache html folder (if it is not set in an Apache vhost.conf file)
documentRoot = "../../../../../htmldocs/" 

#the title for the REST Services Directory pages
title = "REST Services Directory "

class twilio:
    def __init__(self):
        self.twilio_account_sid = "<twilio_account_sid>" 
        self.twilio_auth_token = "<twilio_auth_token>"

class amazon_ses:
    def __init__(self):
        self.AccessKeyID = "<AccessKeyID>" 
        self.SecretAccessKey = '<SecretAccessKey>'

class google_earth_engine:
    def __init__(self):
        self.MY_SERVICE_ACCOUNT = '<MY_SERVICE_ACCOUNT>@developer.gserviceaccount.com'
        self.MY_PRIVATE_KEY_FILE = '<path to private key file (*.pem)>'
        
class dbconnect:
    """ utility module to connect to PG DBs:
    
    Use like this:

>>> from dbconnect import dbconnect
>>> p = dbconnect('species_dev')
>>> p.cur.execute("select max(speciesid) from species")
>>> p.cur.fetchall()
[('9997',)]
>>> del(p)
    
    """
    
    def __init__(self, database=None):
        # the actual connection
        self.conn = None
        
        # the cursor, if available
        self.cur = None
        
        # available connection strings
        self.connections = databases
        
        if database:
            self.open(databases[database]['connectionString'])        

    def open(self, database):  
        """ return a cursor to a PG database """
        try:
            if self.connections.has_key(database):
                self.conn = psycopg2.connect(self.connections[database])
            else:
                self.conn = psycopg2.connect(database)
                
            self.conn.set_isolation_level(0)
    #        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            self.cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)  # get a DictCursor to return updateable rows - the default return type is a list of tuples and tuples are read only
            # return self.cur 
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            # Exit the script and print an error telling what happened.
            raise 
        
    def close(self):
        """ disconnect from the DB server """
        if self.cur and not self.cur.closed:
            self.cur.close()
            self.cur = None
        
        if self.conn:
            self.conn.close()
            self.conn = None

    def __del__(self):
        """ disconnect before deletion """
        self.close() 
