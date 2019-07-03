#!/home/ubuntu//miniconda2/envs/python36/bin/python3.6
# provides a GUI to the REST Services available at JRC that shows you the services based on the schemas that are within 
import tornado, sys, re, datetime, urllib.request, urllib.parse, urllib.error, select, psycopg2, ast, logging, os, colorama, platform, traceback, json, pdfkit
import tornado.options 
import ui_methods
from lxml import etree
from tornado.log import LogFormatter
from collections import OrderedDict
from urllib.parse import parse_qs
from psycopg2 import ProgrammingError, OperationalError
from resources import dbconnect, databases, documentRoot, title
from tornado.web import StaticFileHandler 
from resources import dbconnect, twilio, amazon_ses
# from twilio.rest import TwilioRestClient
# from amazon_ses import AmazonSES, EmailMessage, AmazonError

#=====================  CONSTANTS  ==================================================================================================================================================================================================================

WEBPY_COOKIE_NAME = "webpy_session_id"
PYTHON_REST_SERVER_VERSION = "0.1"

#=====================  CUSTOM CLASSES  ==================================================================================================================================================================================================================

class DopaServicesError(Exception):
    """Exception Class that allows the DOPA Services REST Server to raise custom exceptions"""
    pass

class CustomJSONEncoder(json.JSONEncoder):
    """Class to provide the correct serialisation of decimal values into JSON"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)

#=====================  HELPER FUNCTIONS  ==================================================================================================================================================================================================================
                                   
def getStringValue(value):
    if value is not None:
        return str(value)
    else:
        return ''

def getResultsAsHTML(rows, fieldcount, colsRequired, metadatadict, landscape=False):  # set landscape to True to set orientation to landscape
    data = [[row[col] for col in range(fieldcount) if (col in colsRequired)] for row in rows]
    colnames = "<tr>" + "".join(["<th>" + f["name"] + "</th>" for f in metadatadict["fields"]]) + "</tr>"
    html = "<table>" + colnames + "".join(["<tr>" + p + "</tr>" for p in ["".join(h) for h in [['<td>' + getStringValue(col) + '</td>' for col in row] for row in data]]]) + "</table>" 
    if landscape:
        return "<head><meta name='pdfkit-orientation' content='Landscape'/></head>" + html + "</table>"
    else:
        return html
    
def gettypefrompostgresql(postgresqltype):  # returns a string representation of the SQL data type - this is used to show the data type in the html pages
    if (postgresqltype.lower() in ['integer', 'bigint']): return "integer"
    elif (postgresqltype.lower() in ['boolean']): return "boolean"
    elif (postgresqltype.lower() in ['single precision']): return "single"
    elif (postgresqltype.lower() in ['double precision']): return "double"
    elif (postgresqltype.lower() in ['numeric']): return "numeric"
    elif (postgresqltype.lower() in ['array']): return "array"
    elif (postgresqltype.lower() in ['character varying', 'text']): return "string"
    elif (postgresqltype.lower() in ['date']): return "date"
    elif (postgresqltype.lower() in ['timestamp with time zone']): return "datetime"
    else: return "unknown"

def gettypefromtypecode(typecode):  # returns a string representation of the psycopg2.cursor.type_code value which is shown in the response - the values come from the pg_type table in PostGIS and these are not complete yet - in the output parameter data type section
    if (typecode in [16, 1000, 1560, 1561]): return "boolean"
    elif (typecode in [20, 21, 23]): return "integer"
    elif (typecode in [26, 790, 1005, 1007, 1028, 1016, 1021, 1022, 1700]): return "number"
    elif (typecode in [700, 701]): return "float"
    elif (typecode in [18, 25, 1043, 1002, 1009, 1015, 1043]): return "string"
    elif (typecode in [702, 703, 704, 1023, 1024, 1025, 1082, 1083, 1084, 1182, 1183, 1184, ]): return "date"
    elif (typecode in [17, 22, 24, 27, 28, 29, 30]): return "object"
    elif (typecode in [2278]): return "Null"
    else: return "Undefined"

def getservicedescription(fulldescription):
    pos = fulldescription.find("{")
    if pos > -1:
        return fulldescription[:fulldescription.find("{")]
    else:
        return fulldescription

def isVisibleServiceName(servicename):
    if (servicename[:3] in ['get', 'set']) | (servicename[:6] in ['update', 'insert', 'delete']) | ((servicename[:4] in ['_get', '_set'])) | ((servicename[:7] in ['_update', '_insert', '_delete'])):  
        return True
    else:
        return False

def isValidServiceName(servicename):
    if (servicename[:3] in ['get', 'set']) | (servicename[:6] in ['update', 'insert', 'delete']) | (servicename[:4] in ['_get', '_set']) | (servicename[:7] in ['_update', '_insert', '_delete']):  
        return True
    else:
        return False

#run when the server starts to set all of the global path variables
def _setGlobalVariables():
    global PORT
    global CERTFILE
    global KEYFILE
    global PYTHON_REST_SERVER_VERSION
    global THIS_FOLDER
    THIS_FOLDER = os.path.dirname(os.path.realpath(__file__)) + os.sep
    #initialise colorama to be able to show log messages on windows in color
    colorama.init()
    PORT = "8080"
    CERTFILE = "None"
    KEYFILE = "None"
    #OUTPUT THE INFORMATION ABOUT THE MARXAN-SERVER SOFTWARE
    print("\x1b[1;32;48m\nStarting python-rest-server v" + PYTHON_REST_SERVER_VERSION + " listening on port " + PORT + " ..\x1b[0m")
    #print out which operating system is being used
    print(" Operating system:\t" + platform.system()) 
    print(" Tornado version:\t" + tornado.version)
    #output the ssl information if it is being used
    if CERTFILE != "None":
        print(" SSL certificate file:\t" + CERTFILE)
        testUrl = "https://"
    else:
        print(" SSL certificate file:\tNone")
        testUrl = "http://"
    testUrl = testUrl + "<host>:" + PORT + "/python-rest-server/testTornado"
    if KEYFILE != "None":
        print(" Private key file:\t" + KEYFILE)
    print(" Python executable:\t" + sys.executable)
    print("\x1b[1;32;48mStarted at " + datetime.datetime.now().strftime("%d/%m/%y %H:%M:%S") + "\x1b[0m")
    print("\x1b[1;32;48m\nTo test python-rest-server goto " + testUrl + "\x1b[0m")
        
class PythonRESTHandler(tornado.web.RequestHandler):
    #used by all descendent classes to write the return payload and send it
    def send_response(self, response):
        try:
            #set the return header as json
            self.set_header('Content-Type','application/json')
            #convert the response dictionary to json
            content = json.dumps(response)
        #sometimes the Marxan log causes json encoding issues
        except (UnicodeDecodeError) as e: 
            if 'log' in list(response.keys()):
                response.update({"log": "Server warning: Unable to encode the Marxan log. <br/>" + repr(e), "warning": "Unable to encode the Marxan log"})
                content = json.dumps(response)        
        finally:
            if "callback" in list(self.request.arguments.keys()):
                self.write(self.get_argument("callback") + "(" + content + ")")
            else:
                self.write(content)
    
    #uncaught exception handling that captures any exceptions in the descendent classes and writes them back to the client - RETURNING AN HTTP STATUS CODE OF 200 CAN BE CAUGHT BY JSONP
    def write_error(self, status_code, **kwargs):
        if "exc_info" in kwargs:
            trace = ""
            for line in traceback.format_exception(*kwargs["exc_info"]):
                trace = trace + line
            lastLine = traceback.format_exception(*kwargs["exc_info"])[len(traceback.format_exception(*kwargs["exc_info"]))-1]
            # self.set_status(status_code) #this will return an HTTP server error rather than a 200 status code
            self.set_status(200)
            self.send_response({"error": lastLine, "trace" : trace})
            self.finish()

#tests tornado is working properly
class testTornado(PythonRESTHandler):
    def get(self):
        self.send_response({'info': "Tornado running"})

class getdatabases(PythonRESTHandler):
    def get(self):
        try:
            self.render("templates/databases.html", items=databases, relativepath="")            
        
        except (DopaServicesError, ProgrammingError, OperationalError):
            web.header("Content-Type", "text/html")
            return "DOPA Services Error: " + str(sys.exc_info())        

class getschemas(PythonRESTHandler):
    def get(self, database):
        try:
            conn = dbconnect(database)
            conn.cur.callproc("utils.dopa_rest_getschemas")
            schemas = conn.cur.fetchall()
            schemasdict = [dict([('name', schema[0]), ('description', schema[1])]) for schema in schemas if schema[0] not in ["public","pg_catalog","pg_toast"]]
            self.render("templates/schemas.html", database=database, schemas=schemasdict, relativepath="../")            
        
        except (DopaServicesError, ProgrammingError, OperationalError):
            web.header("Content-Type", "text/html")
            return "DOPA Services Error: " + str(sys.exc_info())        

class getservices(PythonRESTHandler):
    def get(self, database, schema):
        try:
            conn = dbconnect(database)
            conn.cur.callproc("utils.dopa_rest_getservices", [schema])
            services = conn.cur.fetchall()
            servicesdict = [dict([('name', service[0]), ('description', getservicedescription(service[1]))]) for service in services if isVisibleServiceName(service[0])]
            self.render("templates/services.html", database=database, schemaname=schema, services=servicesdict, relativepath="../../")            
        
        except (DopaServicesError, ProgrammingError, OperationalError):
            web.header("Content-Type", "text/html")
            return "DOPA Services Error: " + str(sys.exc_info())        

class getservice(PythonRESTHandler):
    def get(self, database, schema, service):
        try:
            conn = dbconnect(database)
            conn.cur.callproc("utils.dopa_rest_getservice", [service])
            params = conn.cur.fetchall()

            # parse the description text to get the parameters descriptions - the parameter descriptions are encoded using {<param_desc>$<param_desc>$<param_desc> etc}
            paramdesc = []
            paramdescgroups = re.search('{.*}', params[0][1].replace("\n", ""))  # replace line feeds otherwise the regex doesnt work
            if (paramdescgroups):
                paramdesc = paramdescgroups.group(0)[1:-1].split("$")
            # fill in the parameter descriptions if they have not been written
            paramdesc[len(paramdesc):] = ['No description' for i in range(len(params) - len(paramdesc))] 
            
            # parse the function definition for default parameter values
            paramdefs = []
            paramdefsstr = params[0][5]
            if 'DEFAULT ' in paramdefsstr:
                # get the position of the parameter names in the parameter definition string
                pos = [paramdefsstr.find(param[3] + ' ') for param in params if (param[2] == 'IN')]
                # add on the length of the parameter definition to get the last parameter definition
                pos.append(len(paramdefsstr))
                # get the parameter definitions as a list
                paramdefs = [paramdefsstr[pos[i]:pos[i + 1]] for i in range(len(pos) - 1)]
                # remove any trailing spaces with commas
                paramdefs = [(p[:-2] if p[-2:] == ', ' else p) for p in paramdefs]
                # remove the DEFAULT statement
                paramdefs = [(p[p.find('DEFAULT') + 8:] if 'DEFAULT' in p else '') for p in paramdefs]
                # remove the  ARRAY[] statement
                paramdefs = [(p[6:-1] if 'ARRAY' in p else p) for p in paramdefs]
                # remove any typecast symbols, e.g. ::text
#                    paramdefs = [p[:p.find('::')] if '::' in p else p for p in paramdefs] # some are complicated, e.g. ['wdpa_id integer, ', "rlstatus character[] DEFAULT ARRAY['EN'::text, 'CR'::text, 'VU'::text, 'NT'::text, 'LC'::text, 'EX'::text, 'EW'::text, 'DD'::text]"]
                paramdefs = [p.replace("::text", "") for p in paramdefs]
                paramdefs = [p.replace("::integer", "") for p in paramdefs]
                paramdefs = [p.replace("::character varying", "") for p in paramdefs]
                # remove any quotes, e.g. 'CR','DD' -> CR, DD
                paramdefs = [p.replace("'", "") for p in paramdefs]
                # remove any spaces, e.g. CR, DD -> CR,DD
                paramdefs = [p.replace(" ", "") for p in paramdefs]
            # fill in the paramdefs
            paramdefs[len(paramdefs):] = ['' for i in range(len(params) - len(paramdefs))]
#                return params
            # create a dictionary containing the parameter information
            paramsdict = [dict([('mode', params[i][2]), ('name', params[i][3]), ('type', gettypefrompostgresql(params[i][4])), ('description', paramdesc[i]), ('default', paramdefs[i])]) for i in range(len(params))]
            self.render("templates/service.html", database=database, schemaname=schema, servicename=service, servicedesc=getservicedescription(params[0][1]), inparams=[p for p in paramsdict if (p['mode'] == 'IN')], outparams=[p for p in paramsdict if (p['mode'] == 'OUT')], relativepath="../../../")         
        
        except (DopaServicesError, ProgrammingError, OperationalError):
            web.header("Content-Type", "text/html")
            return "DOPA Services Error: " + str(sys.exc_info())

class callservice(PythonRESTHandler):
    def getJsonResponse(self, json):
        self.set_header('Content-Type','application/json')
        if "callback" in list(self.request.arguments.keys()):
            self.write(self.get_argument("callback") + "(" + json + ")")         
        else:
            self.write(json)

    def get(self, database, schema, service):
        try:
            conn = dbconnect(database)
            t1 = datetime.datetime.now()
            # get the input parameters
            params = OrderedDict([(q.split("=")[0], urllib.parse.unquote(q.split("=")[1])) for q in self.request.query.split("&")])
            # get the standard optional parameters from the url 
            format = params.setdefault('format', 'json') 
            fields = params.setdefault('fields', '').split(",")  # fields will be passed as an array, e.g. iucn_species_id,wdpa_id
            includemetadata = params.setdefault('includemetadata', 'true')
            metadataName = params.setdefault('metadataname', 'metadata')
            rootName = params.setdefault('rootname', 'records')
            parseparams = params.setdefault('parseparams', 'true')
            sortField = params.setdefault('sortfield', '')
            decimalPlaceLimit = params.setdefault('dplimit', '2')
            
            # remove the standard optional parameters from the dictionary so we are left with just the parameters required for the function
            del (params['format'], params['fields'], params['includemetadata'], params['parseparams'], params['metadataname'], params['rootname'], params['sortfield'], params['dplimit'])
            if 'callback' in list(params.keys()):
                del(params['callback'])
            # check if the service name is valid
            if not (isValidServiceName(service)):
                raise RESTServicesError('Invalid service')
        
            # PARSE AND CONVERT THE DATA TYPES OF THE OTHER INPUT PARAMETERS
            # get all the parameters for the function from postgresql
            conn.cur.callproc('utils.dopa_rest_getparams', [service])
            # get the function parameters as a string and split this into a list, e.g. wdpa_id integer, presence_id integer[] -->  ['wdpa_id integer', ' presence_id integer[]']
            functionparams = conn.cur.fetchone()
            hasparams = True if functionparams[0] else False
            if hasparams:
                functionparams = functionparams[0].split(',')  
                # get the names of the function parameters which are array types
                arrayparamnames = [p.strip().split(" ")[0] for p in functionparams if '[' in p]
                # convert the array values into lists
                for key in list(params.keys()):
                    if key in arrayparamnames:
                        strlist = params[key].split(",")
                        isnum = isNumeric(strlist[0])
                        if isnum:
                            params[key] = [int(s) for s in strlist]
                        else:
                            params[key] = strlist
                # get the full list of function parameter names
                functionparamnames = [p.strip().split(" ")[0] for p in functionparams]
                # check that all parameters are correct
                invalidparamnames = [n for n in list(params.keys()) if n not in functionparamnames]
                if invalidparamnames and parseparams == 'true':
                    raise RESTServicesError('Invalid parameters: ' + ",".join(invalidparamnames))
                # put the input parameters in the right order 
                params = OrderedDict([(n, params[n]) for n in functionparamnames if n in list(params.keys())])
            
            # GET THE SORT CLAUSE
            if sortField != "":
                sortClause = ' ORDER BY "' + sortField + '"'
            else:
                sortClause = ""
                
            # GET THE FIELDS CLAUSE
            if fields != ['']:
                fieldsClause = ",".join(fields)
            else:
                fieldsClause = "*"
            
            # RUN THE QUERY
            if hasparams :
                sql = "SELECT " + fieldsClause + " from " + schema + "." + service + "(" + ",".join([n + ":=%(" + n + ")s" for n in params]) + ")" + sortClause + ";"  # run the query using named parameters
                conn.cur.execute(sql, params)
            else:
                sql = "SELECT * from " + schema + "." + service + "()" + sortClause + ";" 
                conn.cur.execute(sql)  
            rows = conn.cur.fetchall()
            
            # PROCESS THE ROWS AND WRITE THEM BACK TO THE CLIENT
            conn.cur.close()
            t2 = datetime.datetime.now()
            
            # METADATA SECTION OF RESPONSE
            allfields = [d.name for d in conn.cur.description]
            if (fields == ['']): fields = allfields 
            fieldcount = len(fields)
            fieldsdict = [dict([("name", d.name), ("type", gettypefromtypecode(d.type_code))]) for d in conn.cur.description if (d.name in fields)]
            if len(fieldsdict) != len(fields):
                raise RESTServicesError('Invalid output fields')
            metadatadict = OrderedDict([("duration", str(t2 - t1)), ("error", None), ("idProperty", conn.cur.description[0].name), ("successProperty", 'success'), ("totalProperty", 'recordCount'), ("success", True), ("recordCount", int(conn.cur.rowcount)), ("root", rootName), ("fields", fieldsdict)])    
            
            # RECORDS SECTION OF THE RESPONSE
            # parse the float values and set the correct number of decimal places according to the decimalPlaceLimit variable - dont include lat/long fields as these must have more decimal places
            floatColumns = [i for i, d in enumerate(fieldsdict) if d['type'] == 'float' and d['name'] not in ['lat', 'lng']]
            if len(floatColumns) > 0:
                for floatColumn in floatColumns:
                    for row in rows:
                        if type(row[floatColumn]) != NoneType:  # check that the data is not null
                            row[floatColumn] = round(row[floatColumn], int(decimalPlaceLimit))
                            
            # return the data
            colsRequired = [allfields.index(field) for field in fields]
            if format in ['json', 'array']:
                if format == 'json':
                    recordsdict = [OrderedDict([(allfields[col], row[col]) for col in range(fieldcount) if (col in colsRequired)]) for row in rows] 
                else:
                    recordsdict = [[row[col] for col in range(fieldcount) if (col in colsRequired)] for row in rows]
                json.encoder.FLOAT_REPR = lambda f: ("%.14g" % f)  # this specifies how many decimal places are returned in the json with float values - currently set to 14 - good enough for returning lat/long coordinates
                if (includemetadata.lower() == 'true'):
                    responsejson = json.dumps(dict([(metadataName, metadatadict), (rootName, recordsdict)]), indent=1, cls=CustomJSONEncoder)
                else: 
                    responsejson = json.dumps(dict([(rootName, recordsdict)]), indent=1, cls=CustomJSONEncoder)
                self.getJsonResponse(responsejson)
                
            elif format in ['xml', 'xmlverbose']:
                root = etree.Element('results')
                recordsnode = etree.Element(rootName)
                recordsdicts = [OrderedDict([(allfields[col], str(row[col])) for col in range(fieldcount) if (col in colsRequired) and str(row[col]) != 'None']) for row in rows ]  #
                if format == 'xml':
                    recordselements = [etree.Element('record', element) for element in recordsdicts]
                    for recordelement in recordselements:
                        recordsnode.append(recordelement)
                else:
                    for recordelement in recordsdicts:
                        record = etree.Element('record')
                        for (n, v) in list(recordelement.items()):
                            el = etree.Element(n)
                            el.text = v
                            record.append(el)
                        recordsnode.append(record)
                root.append(recordsnode)
                self.set_header('Content-Type','text/xml')
                self.write(etree.tostring(root))
                
            elif format == 'sms':
                _twilio = twilio()
                client = TwilioRestClient(_twilio.twilio_account_sid, _twilio.twilio_auth_token)  # use the twilio api account
                bodystr = 'Hi Andrew - test species data: '
                bodystr = bodystr + str(rows[0])[:160 - len(bodystr)]
                message = client.sms.messages.create(to="+393668084920", from_="+19712647662", body=bodystr)  # my mobile
                self.set_header('Content-Type','text/plain')
                self.write(message)
    
            elif format == 'email':
                _amazon_ses = amazon_ses()
                amazonSes = AmazonSES(_amazon_ses.AccessKeyID, _amazon_ses.SecretAccessKey)  # use the amazon simple email service api account
                message = EmailMessage()
                message.subject = 'JRC REST Services Information Request'
                message.bodyHtml = getResultsAsHTML(rows, fieldcount, colsRequired, metadatadict) 
                result = amazonSes.sendEmail('a.cottam@gmail.com', 'a.cottam@gmail.com', message)  # to me
                self.set_header('Content-Type','text/plain')
                self.write(result)
                        
            elif format == 'html':
                htmlData = getResultsAsHTML(rows, fieldcount, colsRequired, metadatadict) 
                self.set_header('Content-Type','text/html')
                self.write("<html><head></head><body>" + htmlData + "</body></html>")
            
            elif format == 'csv':
                data = [[row[col] for col in range(fieldcount) if (col in colsRequired)] for row in rows]
                colnames = ",".join([f["name"] for f in metadatadict["fields"]]) + "\n"
                output = colnames + "\n".join([p for p in [",".join(h) for h in [[getStringValue(col) for col in row] for row in data]]])
                filename = "dataDownload.csv" #hardcoded for now
                f = open(THIS_FOLDER + os.sep + 'tmp' + os.sep + filename, 'wb')
                f.write(output)
                f.close()
                self.set_header('Content-Type','text/plain')
                self.set_header("Content-Disposition", "attachment; filename=%s" % filename)
                self.write(output)
    
            elif format == 'pdf':    
                config = pdfkit.configuration(wkhtmltopdf='/usr/local/bin/wkhtmltopdf')
                htmlData = getResultsAsHTML(rows, fieldcount, colsRequired, metadatadict)
                output = pdfkit.from_string(htmlData.decode('utf8'), False, configuration=config, options={'quiet': '', 'encoding': "UTF-8"})
                self.set_header("application/pdf")
                self.write(output)
            
            else:
                raise RESTServicesError('Invalid response format: ' + format)
                
        
        except (DopaServicesError, ProgrammingError, OperationalError):
            web.header("Content-Type", "text/html")
            return "DOPA Services Error: " + str(sys.exc_info())

def make_app():
    return tornado.web.Application([
        ("/python-rest-server/testTornado", testTornado),
        ("/python-rest-server/(.*)/(.*)/(.*)/", getservice),
        ("/python-rest-server/(.*)/(.*)/", getservices),
        ("/python-rest-server/(.*)/(.*)/(.*)", callservice),
        ("/python-rest-server/(.*)/", getschemas),
        ("/python-rest-server/", getdatabases),
        ("/python-rest-server/images/(.*)", StaticFileHandler, {"path": THIS_FOLDER + os.sep + "images" + os.sep}),
        ("/python-rest-server/styles/(.*)", StaticFileHandler, {"path": THIS_FOLDER + os.sep + "styles" + os.sep}),
        ("/python-rest-server/(.*)", StaticFileHandler, {"path": THIS_FOLDER + os.sep}),
    ], websocket_ping_timeout=30, websocket_ping_interval=29, ui_methods=ui_methods)

if __name__ == "__main__":
    #turn on tornado logging 
    tornado.options.parse_command_line() 
    # create an instance of tornado formatter
    my_log_formatter = LogFormatter(fmt='%(color)s[%(levelname)1.1s %(asctime)s.%(msecs)03d]%(end_color)s %(message)s', datefmt='%d-%m-%y %H:%M:%S', color=True)
    # get the parent logger of all tornado loggers 
    root_logger = logging.getLogger()
    # set your format to root_logger
    root_streamhandler = root_logger.handlers[0]
    root_streamhandler.setFormatter(my_log_formatter)
    # logging.disable(logging.ERROR)
    #set the global variables
    _setGlobalVariables()
    app = make_app()
    #start listening on port whatever, and if there is an https certificate then use the certificate information from the server.dat file to return data securely
    if CERTFILE != "None":
        app.listen(PORT, ssl_options={"certfile": CERTFILE,"keyfile": KEYFILE})
        navigateTo = "https://"
    else:
        app.listen(PORT)
        navigateTo = "http://"
    navigateTo = navigateTo + "<host>:" + PORT + "/index.html"
    tornado.ioloop.IOLoop.current().start()