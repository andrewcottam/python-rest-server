# file that handles requests for data from a postgresql database and returns the data in a number of different formats
import psycopg2, exceptions, datetime, logging, urllib, json, web, pdfkit, sys
from psycopg2 import ProgrammingError, DataError, IntegrityError, extensions, OperationalError
from amazon_ses import AmazonSES, EmailMessage, AmazonError
from resources import dbconnect, twilio, amazon_ses
from twilio.rest import TwilioRestClient
from collections import OrderedDict
from decimal import Decimal
from lxml import etree
from types import *

class RESTServicesError(Exception):
    """Exception Class that allows the REST Server to raise custom exceptions"""
    pass  

class CustomJSONEncoder(json.JSONEncoder):
    """Class to provide the correct serialisation of decimal values into JSON"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)

#=====================  CALL SERVICE METHOD TO RETURN DATA FOR A SERVICE  ==================================================================================================================================================================================================================

def callservice(conn, schemaname, servicename, querystring):
    try:  
        t1 = datetime.datetime.now()
        # log the request - not enabled at the moment because of permission issues
#         logging.basicConfig(filename='/srv/www/dopa-services/cgi-bin/logs/REST_Services_Log.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',)
#         logging.info("REST REQUEST: " + web.ctx.home + web.ctx.path + web.ctx.query)
        # PARSE THE STANDARD OPTIONAL INPUT PARAMETERS
        # get the input parameters
        params = getQueryStringParams(querystring)  # the unquoting is to handle encoded parameters (like from extJS - 1,2,3 as a parameter becomes 1%2C2%2C3
        # get the standard optional parameters from the url 
        format = params.setdefault('format', 'json') 
        fields = params.setdefault('fields', '').split(",")  # fields will be passed as an array, e.g. iucn_species_id,wdpa_id
        includemetadata = params.setdefault('includemetadata', 'true')
        metadataName = params.setdefault('metadataname', 'metadata')
        rootName = params.setdefault('rootname', 'records')
        parseparams = params.setdefault('parseparams', 'true')
        sortField = params.setdefault('sortfield', '')
        decimalPlaceLimit = params.setdefault('dplimit', '2')
        isHadoop = ('true' if (servicename[-2:] == '_h') else 'false')  # if the service is a call to a hadoop method then set a flag 

        # remove the standard optional parameters from the dictionary so we are left with just the parameters required for the function
        del (params['format'], params['fields'], params['includemetadata'], params['parseparams'], params['metadataname'], params['rootname'], params['sortfield'], params['dplimit'])
        if 'callback' in params.keys():
            del(params['callback'])
        # check if the service name is valid
        if not (isValidServiceName(servicename)):
            raise RESTServicesError('Invalid servicename')
        
        # authorise with ecas if needed
#         if requiresAuthentication(servicename):
#             if isAuthenticated() == False:
#                 web.ctx.status = '401 Unauthorized'
#                 web.header("Content-Type", "text/html")
#                 return "<html><head></html><body><h1>Authentication required</h1></body></html>"

        # if it is a Hadoop query then we need to run if first before we actually use the values to get the data from postgresql 
        if (isHadoop.lower() == 'true'): 
            hadoopData = runHadoopQuery(conn, servicename, params)
            if hadoopData == '[]': hadoopData = '[-1]'
            servicename = "_" + servicename  # now call the postgresql function
            params.clear()
            params['species_ids'] = str(hadoopData)[1:-1];

        # PARSE AND CONVERT THE DATA TYPES OF THE OTHER INPUT PARAMETERS
        # get all the parameters for the function from postgresql
        conn.cur.callproc('utils.dopa_rest_getparams', [servicename])
        # get the function parameters as a string and split this into a list, e.g. wdpa_id integer, presence_id integer[] -->  ['wdpa_id integer', ' presence_id integer[]']
        functionparams = conn.cur.fetchone()
        hasparams = True if functionparams[0] else False
        if hasparams:
            functionparams = functionparams[0].split(',')  
            # get the names of the function parameters which are array types
            arrayparamnames = [p.strip().split(" ")[0] for p in functionparams if '[' in p]
            # convert the array values into lists
            for key in params.keys():
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
            invalidparamnames = [n for n in params.keys() if n not in functionparamnames]
            if invalidparamnames and parseparams == 'true':
                raise RESTServicesError('Invalid parameters: ' + ",".join(invalidparamnames))
            # put the input parameters in the right order 
            params = OrderedDict([(n, params[n]) for n in functionparamnames if n in params.keys()])
            
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
            sql = "SELECT " + fieldsClause + " from " + schemaname + "." + servicename + "(" + ",".join([n + ":=%(" + n + ")s" for n in params]) + ")" + sortClause + ";"  # run the query using named parameters
            conn.cur.execute(sql, params)
        else:
            sql = "SELECT * from " + schemaname + "." + servicename + "()" + sortClause + ";" 
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
            return getJsonResponse(responsejson)
        
        elif format in ['xml', 'xmlverbose']:
            root = etree.Element('results')
            recordsnode = etree.Element(rootName)
            recordsdicts = [OrderedDict([(allfields[col], str(row[col]).decode('utf-8')) for col in range(fieldcount) if (col in colsRequired) and str(row[col]) != 'None']) for row in rows ]  #
            if format == 'xml':
                recordselements = [etree.Element('record', element) for element in recordsdicts]
                for recordelement in recordselements:
                    recordsnode.append(recordelement)
            else:
                for recordelement in recordsdicts:
                    record = etree.Element('record')
                    for (n, v) in recordelement.items():
                        el = etree.Element(n)
                        el.text = v
                        record.append(el)
                    recordsnode.append(record)
            root.append(recordsnode)
            web.header("Content-Type", "text/xml")
#             web.header("Content-Type", "application/Excel") # doesnt work!
#             web.header("Content-Disposition", "attachment; filename=test.xml")
            return etree.tostring(root)

        elif format == 'sms':
            _twilio = twilio()
            client = TwilioRestClient(_twilio.twilio_account_sid, _twilio.twilio_auth_token)  # use the twilio api account
            bodystr = 'Hi Andrew - test species data: '
            bodystr = bodystr + str(rows[0])[:160 - len(bodystr)]
            message = client.sms.messages.create(to="+393668084920", from_="+19712647662", body=bodystr)  # my mobile
            return message

        elif format == 'email':
            _amazon_ses = amazon_ses()
            amazonSes = AmazonSES(_amazon_ses.AccessKeyID, _amazon_ses.SecretAccessKey)  # use the amazon simple email service api account
            message = EmailMessage()
            message.subject = 'JRC REST Services Information Request'
            message.bodyHtml = getResultsAsHTML(rows, fieldcount, colsRequired, metadatadict) 
            result = amazonSes.sendEmail('a.cottam@gmail.com', 'a.cottam@gmail.com', message)  # to me
            return result 
                    
        elif format == 'html':
            htmlData = getResultsAsHTML(rows, fieldcount, colsRequired, metadatadict) 
            web.header("Content-Type", "text/html") 
            return "<html><head></head><body>" + htmlData + "</body></html>"
        
        elif format == 'csv':
            data = [[row[col] for col in range(fieldcount) if (col in colsRequired)] for row in rows]
            colnames = ",".join([f["name"] for f in metadatadict["fields"]]) + "\n"
            output = colnames + "\n".join([p for p in [",".join(h) for h in [[getStringValue(col) for col in row] for row in data]]])
            filename = "dataDownload.csv" #hardcoded for now
            f = open(r'/tmp/' + filename, 'wb')
            f.write(output)
            f.close()
            web.header("Content-Type", "text/plain")
            web.header("Content-Disposition", "attachment; filename=%s" % filename)
            return output

        elif format == 'pdf':    
            config = pdfkit.configuration(wkhtmltopdf='/usr/local/bin/wkhtmltopdf')
            web.header("Content-Type", "application/pdf")
            htmlData = getResultsAsHTML(rows, fieldcount, colsRequired, metadatadict)
            return pdfkit.from_string(htmlData.decode('utf8'), False, configuration=config, options={'quiet': '', 'encoding': "UTF-8"})
        
        else:
            raise RESTServicesError('Invalid response format: ' + format)

    except (RESTServicesError, DataError, ProgrammingError, exceptions.TypeError, IndexError, IntegrityError, AmazonError, OperationalError) as e:
#        web.webapi.internalerror() #returns a internal server error 500
        t2 = datetime.datetime.now()
        msg = "There was an error sending the email. Make sure that the email address has been verified in Amazon Simple Email Services" if type(e) == AmazonError else e.message
        logging.error(msg + "\n")
        if type(e) == ProgrammingError:
            if ("column" in e.message) & ("does not exist" in e.message) & (sortField != ""):
                msg = "Invalid sortfield parameter: " + sortField
        return returnError(metadataName, rootName, t2 - t1, msg)

def getQueryStringParams(querystring):
    return OrderedDict([(q.split("=")[0], urllib.unquote(q.split("=")[1])) for q in querystring.split("&")])

def isValidServiceName(servicename):
    if (servicename[:3] in ['get', 'set']) | (servicename[:6] in ['update', 'insert', 'delete']) | (servicename[:4] in ['_get', '_set']) | (servicename[:7] in ['_update', '_insert', '_delete']):  
        return True
    else:
        return False

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
    
def getJsonResponse(json):
    callback = web.input().setdefault('callback', None)
    if callback:
        web.header("Content-Type", "application/javascript") 
        return callback + '(' + json + ');'                 
    else:
        web.header("Content-Type", "application/json") 
        return json
   
def isNumeric(val):
    try:
        i = float(val)
    except ValueError, TypeError:
        return False
    else:
        return True

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
    
def functionExists(conn, functionName):
    conn.cur.callproc("utils.dopa_rest_function_exists", [functionName])
    result = conn.cur.fetchall()
    return result[0]=='t'

def returnError(metadataName, rootName, duration, message):
    metadatadict = OrderedDict([("duration", str(duration)), ("error", message), ("idProperty", None), ("successProperty", 'success'), ("totalProperty", 'recordCount'), ("success", False), ("recordCount", 0), ("root", None), ("fields", None)])    
    responsejson = json.dumps(dict([(metadataName, metadatadict), (rootName, None)]), indent=1)
    return getJsonResponse(responsejson)
