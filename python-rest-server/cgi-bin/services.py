#!/usr/bin/env python 
# provides a GUI to the REST Services available at JRC that shows you the services based on the schemas that are within 
import web, sys, re, datetime, urllib, select, psycopg2, ast, serviceRequest
# import pycas
from serviceRequest import RESTServicesError
from urlparse import parse_qs
from psycopg2 import ProgrammingError, OperationalError
from resources import dbconnect, databases, documentRoot, title

#=====================  CONSTANTS  ==================================================================================================================================================================================================================

CAS_SERVER = "https://intragate.ec.europa.eu"
WEBPY_COOKIE_NAME = "webpy_session_id"

#=====================  URL HANDLERS  ==================================================================================================================================================================================================================

urls = (
  "/terms", "terms",
  "/manager", "manager",
  "/endSession", "endSession",
  "/ecasLogin", "ecasLogin",
  "/ecasProxyLogin", "ecasProxyLogin",
  "/ecasLogout", "ecasLogout",
  "/(.+)/(.+)/(.+)", "getservice",
  "/(.+)/(.+)/", "getservices",
  "/(.+)/", "getschemas",
  "/", "getdatabases"
  )

app = web.application(urls, locals()) 
# session = web.session.Session(app, web.session.DiskStore('../../htdocs/mstmp/restSessions')) //causing Internal Server Errors 
#e.g.  [Thu Mar 19 15:10:27 2015] [error] [client 139.191.170.67] OSError: [Errno 2] No such file or directory: '../../htdocs/mstmp/restSessions/fadb4414da20b8cf9201dcf90fcb4f15b8f71e60', referer: http://127.0.0.1:8020/species_validation_tool/index.html?wdpaid=785  

#=====================  CUSTOM ERROR CLASSES  ==================================================================================================================================================================================================================

class DopaServicesError(Exception):
    """Exception Class that allows the DOPA Services REST Server to raise custom exceptions"""
    pass

#=====================  GET PROVIDERS CLASS  ==================================================================================================================================================================================================================

class getdatabases:
    def GET(self):
        try:
            render = web.template.render('templates/')
            return render.getdatabases(sorted(databases),databases, render.header(documentRoot, title), render.footer(documentRoot))
        
        except (DopaServicesError, ProgrammingError, OperationalError):
            web.header("Content-Type", "text/html")
            return "DOPA Services Error: " + str(sys.exc_info())        


#=====================  GET SCHEMAS CLASS  ==================================================================================================================================================================================================================

class getschemas:
    def GET(self, database):
        try:
            render = web.template.render('templates/')
            conn = dbconnect(database)
            conn.cur.callproc("utils.dopa_rest_getschemas")
            schemas = conn.cur.fetchall()
            schemasdict = [dict([('name', schema[0]), ('description', schema[1])]) for schema in schemas if schema[0] not in ["public","pg_catalog","pg_toast"]]
            return render.getschemas(database, schemasdict, render.header(documentRoot, title), render.footer(documentRoot))
        
        except (DopaServicesError, ProgrammingError, OperationalError):
            web.header("Content-Type", "text/html")
            return "DOPA Services Error: " + str(sys.exc_info())

#=====================  GET SERVICES CLASS  ==================================================================================================================================================================================================================

class getservices:
    def GET(self, database, schemaname):
        try:
            render = web.template.render('templates/')
            conn = dbconnect(database)
            conn.cur.callproc("utils.dopa_rest_getservices", [schemaname])
            services = conn.cur.fetchall()
            servicesdict = [dict([('name', service[0]), ('description', getservicedescription(service[1]))]) for service in services if isVisibleServiceName(service[0])]
            return render.getservices(database, schemaname, servicesdict, render.header(documentRoot, title), render.footer(documentRoot))

        except (DopaServicesError, ProgrammingError, OperationalError):
            web.header("Content-Type", "text/html")
            return "DOPA Services Error: " + str(sys.exc_info())

#=====================  GET SERVICE CLASS  ==================================================================================================================================================================================================================

class getservice:
    def GET(self, database, schemaname, servicename):
        # if there are some parameters then the user is making a request for data 
        conn = dbconnect(database)
        if web.input():
            return serviceRequest.callservice(conn, schemaname, servicename, web.ctx.query[1:])  # pass the querystring to preserve the order of the parameters - the web.input() collection does not preserve the order
        else:
            try:
                render = web.template.render('templates/')
                conn.cur.callproc("utils.dopa_rest_getservice", [servicename])
                params = conn.cur.fetchall()
                if (len(params) == 0):
                    raise DopaServicesError('No parameters found for service ' + servicename)
                
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
                return render.getservice(database, schemaname, servicename, getservicedescription(params[0][1]), [p for p in paramsdict if (p['mode'] == 'IN')], [p for p in paramsdict if (p['mode'] == 'OUT')], render.header(documentRoot, title), render.footer(documentRoot))
            
            except (DopaServicesError, ProgrammingError, OperationalError):
                web.header("Content-Type", "text/html")
                return "DOPA Services Error: " + str(sys.exc_info())

#=====================  OTHER CLASSES  ==================================================================================================================================================================================================================

class manager:
    def GET(self):
        try:
            render = web.template.render('templates/')
            conn = dbconnect("ibex")
            conn.cur.execute("select * from especies.species_wdpa_log")
            rows = conn.cur.fetchall()
            return render.manager(rows, render.header_manager(), render.footer_manager())
        
        except (DopaServicesError, ProgrammingError, OperationalError):
            web.header("Content-Type", "text/html")
            return "DOPA Services Error: " + str(sys.exc_info())

class terms:
    def GET(self):
        render = web.template.render('templates/')
        return render.terms(render.header(documentRoot, title), render.footer(documentRoot)) 
      
#=====================  HELPER FUNCTIONS  ==================================================================================================================================================================================================================
                                   
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

def getservicedescription(fulldescription):
    pos = fulldescription.find("{")
    if pos > -1:
        return fulldescription[:fulldescription.find("{")]
    else:
        return fulldescription

def isVisibleServiceName(servicename):
    if (servicename[:3] in ['get', 'set']) | (servicename[:6] in ['update', 'insert', 'delete']) | ((servicename[:4] in ['_get', '_set']) & (web.ctx.host == 'dopa-services.jrc.it')) | ((servicename[:7] in ['_update', '_insert', '_delete']) & (web.ctx.host == 'dopa-services.jrc.it')):  
        return True
    else:
        return False

def runHadoopQuery(conn, functionname, params): 
    try:
        conn.cur.execute("INSERT INTO hadoop_jobs(id, functionname, params) VALUES (DEFAULT,'" + functionname + "','" + params['quadkey'] + "') RETURNING id")
        job_id = conn.cur.fetchone()[0]  # this is the job_id value from the table
        conn.cur.execute("LISTEN hadoop_job_complete;")  # listen for the results to be posted back
        conn.cur.execute("NOTIFY hadoop_job_request,'" + str(job_id) + "," + functionname + "," + params['quadkey'] + "'")
        while 1:
            if select.select([conn.conn], [], [], 5) == ([], [], []):
                assert 'nothing'
            else:
                conn.conn.poll()
                while conn.conn.notifies:  # results posted back
                    conn.cur.execute("UNLISTEN hadoop_job_complete;")
                    resultsDict = ast.literal_eval(conn.conn.notifies.pop().payload)
                    return resultsDict['results']
    except (DopaServicesError, OperationalError):
        web.header("Content-Type", "text/html")
        return "DOPA Services Error: " + str(sys.exc_info())

#===============================================   AUTHENTICATION SERVER =============================================================================================================================================

def requiresAuthentication(servicename):
    if (servicename[:3] in ['set']) | ((servicename[:4] == '_set') & (web.ctx.host == 'dopa-services.jrc.it')):
        return True
    else:
        return False

def isAuthenticated():
    cookie = web.cookies().get(WEBPY_COOKIE_NAME)
    if cookie == None:
        return False
    # else:
    #     if "loggedin" not in session.keys():
    #         return False
    #     if session.loggedin == False:
    #         return False
    #     username = session.username
    #     return True

# class ecasLogin:  # logs into ECAS and sets the session variables
#     def GET(self):
#         status, id, cookie = pycas.login(CAS_SERVER, web.ctx.home + web.ctx.path)  
#         if status == 0:
#             session.loggedin = True
#             session.username = cookie[cookie.rfind(':') + 1:cookie.find(';')]
#             session.ip = web.ctx.ip
#             return "ECAS authentication successful (webpy session_id: " + session.session_id + ", username: " + session.username + ", ip: " + session.ip + ")" 
#         if status == 1:
#             return "ECAS cookie exceeded its lifetime"
#         if status == 2:
#             return "ECAS cookie is invalid (probably corrupted)"
#         if status == 3:
#             return "ECAS server ticket invalid"
#         if status == 4:
#             return "ECAS server returned without ticket while in gateway mode"
# 
# class ecasProxyLogin:  # proxy logs into ECAS and sets the session variables
#     def GET(self):
#         service_url = web.ctx.home + web.ctx.path
#         cas_url = CAS_SERVER + "/cas/login?service=" + service_url
#         if opt in ("renew", "gateway"):
#             cas_url += "&%s=true" % opt
#         #  Print redirect page to browser
#         print "Refresh: 0; url=%s" % cas_url
#         print "Content-type: text/html"
#         if opt == "gateway":
#             domain, path = urlparse.urlparse(service_url)[1:3]
#             print make_pycas_cookie("gateway", domain, path, secure)
#         print """
#     If your browser does not redirect you, then please follow <a href="%s">this link</a>.
#     """ % (cas_url)
#         raise SystemExit
#         response = urllib.urlopen(CAS_SERVER + "/cas/login?service=" + serviceurl)
#         return response
#         status, id, cookie = pycas.login(CAS_SERVER, serviceurl)
#         if status == 0:
#             session.loggedin = True
#             session.username = cookie[cookie.rfind(':') + 1:cookie.find(';')]
#             session.ip = web.ctx.ip
#             ticket = web.ctx.query[1:].split("=")[1]
#             response = urllib.urlopen(CAS_SERVER + "/serviceValidate?ticket=" + ticket + "&service=" + serviceurl + "&pgtUrl=https://foo.bar.com/pgtCallback")
#             return response
#             return "ECAS authentication successful (webpy session_id: " + session.session_id + ", username: " + session.username + ", ip: " + session.ip + ")" 
# 
# class endSession:  # ends the session and logs out
#     def GET(self):
#         session.loggedin = False
#         session.kill()
#         return "webpy session_id: " + session.session_id + " ended"
#     
# class ecasLogout():  # redirects to the ecas logout page to end an ECAS session
#     def GET(self):
#         web.redirect(CAS_SERVER + "/cas/logout") 

if __name__ == "__main__":
    app.run()
