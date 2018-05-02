# Python module that wraps all of the Google Earth Engine functionality. This class returns all results as dictionaries either for internal Python use or for returning in other formats to the web
import sys, ee, cPickle, utilities, math, datetime, time, json, os, oauth2client
from resources import google_earth_engine
from orderedDict import OrderedDict
from ee import EEException
from Simonets_libs import PBS_classification, PINO, PBS_palette
# Constants
cloudNDVIThreshold = 0.1  # Pixels with an NDVI lower than this threshold may be clouds
snowNorthThreshold = 31  # Pixels with a latitude further north than this will be tested for snow
snowAltitudinalThreshold = 3000  # Pixels with a height greater than this will be tested for snow
snowValueThreshold = 0.18  # Pixels with a value greater than this will be tested for snow 
snowSatThreshold = 0.58  # Pixels with a Sat lower than this will be considered as snow && (default value:0.58) 
snowTemperatureThreshold = 281  # Pixels with a temperature less than this will be tested for snow 
slopeMaskThreshold = 0.17  # Pixels with a slope greater than this threshold in radians will be excluded
ndviMaskThreshold = 0.12  # Pixels with an NDVI greater than this threshold will be excluded
annualMaxTempThreshold = 310  # Threshold for the max annual temperature above which bare rock could be present
annualMaxNDVIThreshold = 0.14  # Threshold for the max annual NDVI below which bare rock will be present
lowerSceneTempThreshold = 264  # lower temperature threshold for the scene
upperSceneTempThreshold = 310  # upper temperature threshold for the scene
sunElevationThreshold = 23  # Landsat scenes with a solar elevation angle greater than this angle will be included
class OAuthInfo(object):
    # lifted straight from https://code.google.com/p/earthengine-api/source/browse/python/ee/oauthinfo.py
  SCOPE = 'https://www.googleapis.com/auth/earthengine.readonly'
  CLIENT_ID = ('517222506229-vsmmajv00ul0bs7p89v5m89qs8eb9359.apps.googleusercontent.com')
  CLIENT_SECRET = 'RUP0RZ6e0pPhDzsqIJ7KlNd1'

waterDetectExpressions = [
  {"bands":"SWIR2,NIR,Red", "expression":"((b('h')<(-16.481702483844295*b('v'))+237.39299348280895)&&(b('h')<(84688.07188433492*b('v'))-563.0010063926386)&&(b('h')>(1367.4216031588037*b('v'))+190.57398940093609))||((b('h')>(13.55095876285446*b('v'))+202.81876979706576)&&(b('h')<(-53.2340279866469*b('v'))+238.63636595740172)&&(b('h')<(1367.4216031588037*b('v'))+190.57398940093609))||((b('h')>(1599.6635800374377*b('v'))-647.8326130760333)&&(b('h')<(4.6138461972494085*b('v'))+236.679307363423)&&(b('h')>(-53.2340279866469*b('v'))+238.63636595740172))||((b('h')>(4.6138461972494085*b('v'))+236.679307363423)&&(b('h')<(4.062613097521557*b('v'))+236.9849857615982)&&(b('h')<(14.217951737090626*b('v'))+236.35438967976754))||((b('h')<(-13.951882699724406*b('v'))+246.9746656664425)&&(b('h')<(483.90327387870934*b('v'))+207.18926438479662)&&(b('h')>(4.062613097521557*b('v'))+236.9849857615982))||((b('h')<(-20.469908836263855*b('v'))+250.5891434430224)&&(b('h')<(4.658797190131653*b('v'))+245.48741910936977)&&(b('h')>(-13.951882699724406*b('v'))+246.9746656664425))||((b('h')>(210.80364213633263*b('v'))+97.02976992627356)&&(b('h')<(13.55095876285446*b('v'))+202.81876979706576)&&(b('h')>(1.1522186650929778*b('v'))+202.93090743023936))||((b('h')<(1.1522186650929778*b('v'))+202.93090743023936)&&(b('h')>(-71.79923381426251*b('v'))+203.59070053446678)&&(b('h')>(141.4836523127315*b('v'))+132.0453479392211))||((b('h')<(-71.79923381426251*b('v'))+203.5907005344668)&&(b('h')>(-79.04981968510809*b('v'))+203.65627683756435)&&(b('h')>(10.857445113377223*b('v'))+175.86366933371292))||((b('h')<(-79.04981968510809*b('v'))+203.65627683756435)&&(b('h')>(-91.44418331006706*b('v'))+203.768374888708)&&(b('h')>(16.605504291045854*b('v'))+174.08679898856425))||((b('h')>(-1020.1010656054937*b('v'))+212.16740446670389)&&(b('h')>(99.74988069193253*b('v'))+151.24678738275915)&&(b('h')<(-91.44418331006706*b('v'))+203.768374888708))||((b('h')>(2149.754329876662*b('v'))-411.89563352584287)&&(b('h')<(99.74988069193253*b('v'))+151.24678738275912)&&(b('h')>(41.62121011013503*b('v'))+154.4090247267743))||((b('h')>(177.29444892391095*b('v'))+117.96332477544951)&&(b('h')<(41.62121011013503*b('v'))+154.4090247267743)&&(b('h')>(22.61526070734314*b('v'))+155.44296068915622))||((b('h')<(22.61526070734314*b('v'))+155.44296068915622)&&(b('h')>(-3.5222556628157378*b('v'))+156.86485851544862)&&(b('h')>(183.05939965647218*b('v'))+116.56644483957649))||((b('h')<(-3.5222556628157378*b('v'))+156.86485851544862)&&(b('h')>(-45.58838956872646*b('v'))+159.15328345660438)&&(b('h')>(120.59366417838626*b('v'))+130.0579643812797))||((b('h')>(-79.27784668768453*b('v'))+160.98601175289758)&&(b('h')>(18.192621481728114*b('v'))+147.98644067414764)&&(b('h')<(-45.58838956872646*b('v'))+159.15328345660438))||((b('h')>(-249.8453350157328*b('v'))+170.26499363683433)&&(b('h')>(27.32683351734562*b('v'))+146.76821693073646)&&(b('h')<(-79.27784668768453*b('v'))+160.9860117528976))||((b('h')<(-1020.1010656054937*b('v'))+212.16740446670389)&&(b('h')>(-3999.1589500935984*b('v'))+239.1108275580515)&&(b('h')>(224.31551905409455*b('v'))+144.47033594378084))||((b('h')<(-3894.4662440381876*b('v'))+368.5347326130829)&&(b('h')<(224.31551905409455*b('v'))+144.47033594378084)&&(b('h')>(-66.42201716418424*b('v'))+150.98524293787293))||((b('h')<(141.4836523127315*b('v'))+132.0453479392211)&&(b('h')>(-37.942684535992605*b('v'))+192.23358323472317)&&(b('h')>(192.66969319288907*b('v'))+106.18976411449788))||((b('h')>(2692.244260520529*b('v'))-1156.41931133637)&&(b('h')<(192.66969319288907*b('v'))+106.18976411449788)&&(b('h')>(-33.044398171145254*b('v'))+190.40598286857332))||((b('h')>(-18.095741855627164*b('v'))+183.0184247191252)&&(b('h')<(-33.044398171145254*b('v'))+190.40598286857332)&&(b('h')>(-190.0052894840852*b('v'))+248.96968475693268))||((b('h')<(-18.095741855627164*b('v'))+183.0184247191252)&&(b('h')>(-20.357709587580604*b('v'))+183.88620445646478)&&(b('h')>(-10.857445113376142*b('v'))+179.44129129939233))||((b('h')<(-20.357709587580604*b('v'))+183.88620445646478)&&(b('h')>(-271.436127834409*b('v'))+280.2097553011579)&&(b('h')>(15.51063587625202*b('v'))+167.10438947568133))||((b('h')>(26.93640963242224*b('v'))+161.75858334192242)&&(b('h')<(15.51063587625202*b('v'))+167.10438947568133)&&(b('h')>(-13.837920242538257*b('v'))+178.67266483567965))"},
  {"bands":"SWIR2,NIR,Red", "expression":"((b('h')>(15.009416604134271*b('s'))+202.36255490978616)&&(b('h')<(-36.29216171095232*b('s'))+253.66413322487273)&&(b('h')<(1293.2135298349533*b('s'))-123.40004846221527))||((b('h')<(4.766693079016967*b('s'))+242.01933653025537)&&(b('h')>(-36.29216171095232*b('s'))+253.66413322487273)&&(b('h')>(10000000*b('s'))-9999782.628028486))||((b('h')>(1770.2933626478894*b('s'))-1552.9213911339689)&&(b('h')<(15.009416604134271*b('s'))+202.36255490978616)&&(b('h')>(4.4527608324114265*b('s'))+205.053020095668))||((b('h')<(4.4527608324114265*b('s'))+205.053020095668)&&(b('h')>(-11.642292182700958*b('s'))+209.1549990498435)&&(b('h')>(29426.209672458182*b('s'))-29085.64044956417))||((b('h')<(-11.642292182700958*b('s'))+209.1549990498435)&&(b('h')>(-42.610608506107866*b('s'))+217.04757210850875)&&(b('h')>(18827.416804554992*b('s'))-18538.35359451796))||((b('h')<(-42.610608506107866*b('s'))+217.04757210850875)&&(b('h')>(-2948.5423727959624*b('s'))+957.65221181953)&&(b('h')>(12.555041960589588*b('s'))+162.21702616003503))||((b('h')<(12.555041960589588*b('s'))+162.21702616003503)&&(b('h')>(-5.800507114530911*b('s'))+167.1478499531627)&&(b('h')>(340.2498970280048*b('s'))-163.48724190980542))||((b('h')<(-5.800507114530911*b('s'))+167.1478499531627)&&(b('h')>(-17.238360348487014*b('s'))+170.22038342178752)&&(b('h')>(114.72489873171403*b('s'))+51.991421419182984))||((b('h')<(-17.238360348487014*b('s'))+170.22038342178752)&&(b('h')>(-23.671165603568785*b('s'))+171.94841831077412)&&(b('h')>(7.274223651467424*b('s'))+148.2589876324115))||((b('h')<(-23.671165603568785*b('s'))+171.94841831077412)&&(b('h')>(-32.91623240087615*b('s'))+174.43190682678946)&&(b('h')>(13.384571518699898*b('s'))+143.58137116979333))||((b('h')<(-32.91623240087615*b('s'))+174.43190682678946)&&(b('h')>(-947.3302286013217*b('s'))+420.0695758925139)&&(b('h')>(10.999060906509083*b('s'))+145.17085286279737))||((b('h')<(10.999060906509083*b('s'))+145.17085286279737)&&(b('h')>(-8.45159799505535*b('s'))+150.75031427827042)&&(b('h')>(24.745610366995415*b('s'))+136.0114349177433))||((b('h')<(-8.45159799505535*b('s'))+150.75031427827042)&&(b('h')>(-221.45381967303496*b('s'))+211.8504386121941)&&(b('h')>(26.728949128935337*b('s'))+135.13087320229778))"},
  {"bands":"SWIR2,Green,Blue", "expression":"((b('h')<(12.26593689219973*b('s'))+213.56319793892735)&&(b('h')<(161.55657816363095*b('s'))+166.50682005437122)&&(b('h')>(62.88747617389189*b('s'))+192.89228050816078))||((b('h')>(-9715.48675311279*b('s'))+2807.7626028916543)&&(b('h')>(119.40987056283161*b('s'))+169.81179413848707)&&(b('h')<(62.88747617389189*b('s'))+192.89228050816078))||((b('h')>(-317.05551175659076*b('s'))+286.882084995492)&&(b('h')>(244.34605806690413*b('s'))+118.79505990525014)&&(b('h')<(119.40987056283161*b('s'))+169.81179413848707))||((b('h')<(244.34605806690413*b('s'))+118.79505990525013)&&(b('h')>(38.657063321438876*b('s'))+180.37958883957006)&&(b('h')<(0.7855098741218717*b('s'))+218.25114228688705))||((b('h')>(59.99027169469099*b('s'))+159.04638046631794)&&(b('h')<(38.657063321438876*b('s'))+180.37958883957006)&&(b('h')>(-70.42121412059574*b('s'))+213.03828475836497))||((b('h')<(59.99027169469099*b('s'))+159.04638046631794)&&(b('h')>(-63.190713604259756*b('s'))+210.04477165312707)&&(b('h')>(71.3322190203302*b('s'))+147.70443314067873))||((b('h')<(71.3322190203302*b('s'))+147.70443314067873)&&(b('h')>(-132.8395919398703*b('s'))+242.32131043905457)&&(b('h')>(97.78926528286257*b('s'))+121.24738687814636))||((b('h')>(-55.64206460129677*b('s'))+201.7946927528083)&&(b('h')>(10000000*b('s'))-9999853.847371848)&&(b('h')<(97.78926528286257*b('s'))+121.24738687814636))||((b('h')<(-55.64206460129677*b('s'))+201.7946927528083)&&(b('h')>(-70.89697101755921*b('s'))+209.8031067718208)&&(b('h')>(-26.931356210984664*b('s'))+173.08398436249618))||((b('h')>(-26.262128232850145*b('s'))+172.5250597538679)&&(b('h')<(-70.89697101755921*b('s'))+209.8031067718208)&&(b('h')>(-361.4610456160576*b('s'))+362.3414013335865))||((b('h')<(-26.262128232850145*b('s'))+172.5250597538679)&&(b('h')>(-49.10093639625872*b('s'))+185.4582131347398)&&(b('h')>(-1.561849811608879*b('s'))+151.8959260346158))||((b('h')<(-26.931356210984664*b('s'))+173.08398436249618)&&(b('h')>(-38.71382455329052*b('s'))+182.92444489622275)&&(b('h')>(4.488559368497584*b('s'))+141.66406878301393))||((b('h')>(-38.65578283731854*b('s'))+199.88701886395202)&&(b('h')<(-70.42121412059574*b('s'))+213.03828475836497)&&(b('h')>(-214.9227838798176*b('s'))+256.30292861985987))||((b('h')<(-317.05551175659076*b('s'))+286.882084995492)&&(b('h')>(-717.4513294606268*b('s'))+394.2776694687533)&&(b('h')>(-124.55752247580413*b('s'))+229.2470228701161))"}
]
sensors = [
  {"name":"Landsat 5", "collectionid":"LANDSAT/L5_L1T_TOA", "startDate":"8/13/1983", "endDate":"10/15/1984", "bands": {"Blue": "B1", "Green": "B2", "Red": "B3", "NIR": "B4", "SWIR1": "B5", "SWIR2": "B7", "TIR": "B6"}},
  {"name":"Landsat 7", "collectionid":"LANDSAT/LE7_L1T_TOA", "startDate":"8/13/2012", "endDate":"10/15/2012", "bands": {"Blue": "B1", "Green": "B2", "Red": "B3", "NIR": "B4", "SWIR1": "B5", "SWIR2": "B7", "TIR": "B6_VCID_2"}},
  {"name":"Landsat 8", "collectionid":"LANDSAT/LC8_L1T_TOA", "startDate":'8/22/2014', "endDate":'9/12/2014', "bands": {"Blue": "B2", "Green": "B3", "Red": "B4", "NIR": "B5", "SWIR1": "B6", "SWIR2": "B7", "TIR": "B10"}}
]
class GoogleEarthEngineError(Exception):
    """Exception Class that allows the DOPA Services REST Server to raise custom exceptions"""
    pass  
 
def getSensorInformation(scene):  # returns the sensor information based on the passed scene
#     logging.info(scene.getInfo().keys())
    try:
        if "SENSOR_ID" not in scene.getInfo()['properties'].keys():
            return None
        else:
            sensorname = scene.getInfo()['properties']['SENSOR_ID']
            if sensorname == "OLI_TIRS":  # landsat 8
                return sensors[2]
            elif (sensorname == "ETM+") | (sensorname == "ETM"):  # landsat 7
                return sensors[1]
            elif sensorname == "TM":  # landsat 5
                return sensors[0]
    except (EEException)as e:
        raise GoogleEarthEngineError("Unable to get sensor information. You may be calling this method from an imageCollection.map() function which does not support getInfo()")
    
def getRadiometricCorrection(scene):
    sceneid = landsat_scene.getInfo()['id']
    if "L5_L1T/" in sceneid:
        return 0.02
    if "L7_L1T/" in sceneid:
        return 10000
    if "LC8_L1T/" in sceneid:
        return 1

def getGEEBandNames(bands, sensor):  # gets the corresponding gee band names from their descriptions, e.g. SWIR2,NIR,Red -> B7,B5,B4 for Landsat 8 object
    geebandnames = []
    bandnames = bands.split(",")
    for band in bandnames:
        geebandnames.append(sensor['bands'][band])
    return ",".join([b for b in geebandnames])
        
def getImage(ll_x, ll_y, ur_x, ur_y, crs, width, height, layerParameters):  # main method to retrieve a url for an image generated from google earth engine 
#     logging.basicConfig(filename='../../htdocs/mstmp/earthEngine.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',)
    authenticate()
    region = getBoundingBoxLL(ll_x, ll_y, ur_x, ur_y, crs)
    if layerParameters['sceneid'] == 'collection':
        # GET A COLLECTION TO CREATE AN IMAGE FOR
        layerParameters.setdefault("collectionid", "LANDSAT/LC8_L1T_TOA")
        layerParameters.setdefault("startDate", "2013-09-13")
        layerParameters.setdefault("endDate", "2013-10-15")
        sd = datetime.datetime(int(layerParameters['startDate'][:4]), int(layerParameters['startDate'][5:7]), int(layerParameters['startDate'][8:10]))
        ed = datetime.datetime(int(layerParameters['endDate'][:4]), int(layerParameters['endDate'][5:7]), int(layerParameters['endDate'][8:10]))
        try:
            landsat_collection = ee.ImageCollection(layerParameters['collectionid']).filterBounds(ee.Feature.Polygon(region)).filterDate(sd, ed)
            if len(landsat_collection.getInfo()['features']) != 0:
                scene = landsat_collection.median()
                sensorinfo = getSensorInformation(ee.Image(landsat_collection.getInfo()['features'][0]['id']))  # get the scene metadata from the first scene in the collection
            else:
#                 logging.error("getImage: No matching scenes")
                raise GoogleEarthEngineError("getImage: No matching scenes")
        except (GoogleEarthEngineError):
#             logging.error("Google Earth Engine Services Error: " + str(sys.exc_info()))
            return "Google Earth Engine Services Error: " + str(sys.exc_info())
    elif layerParameters['sceneid'] == "dario":
        layerParameters.setdefault("collectionid", "LANDSAT/LC8_L1T_TOA")
        layerParameters.setdefault("startDate", "2013-09-13")
        layerParameters.setdefault("endDate", "2013-10-15")
        sd = datetime.datetime(int(layerParameters['startDate'][:4]), int(layerParameters['startDate'][5:7]), int(layerParameters['startDate'][8:10]))
        ed = datetime.datetime(int(layerParameters['endDate'][:4]), int(layerParameters['endDate'][5:7]), int(layerParameters['endDate'][8:10]))
        collectionL8 = (ee.ImageCollection(layerParameters['collectionid']).filterDate(sd, ed).filterMetadata('CLOUD_COVER', "less_than", 80).filterBounds(ee.Feature.Polygon(region)).map(PINO(['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'BQA'])))
        out = PBS_classification(collectionL8)
        output_thumbnail = out.getThumbUrl({'region':region, 'dimensions': width + 'x' + height, 'palette':PBS_palette})
        return output_thumbnail
    else:
        try:
            # GET THE SINGLE SCENE TO CREATE AN IMAGE FOR
            scene = ee.Image(layerParameters['sceneid'])
            sensorinfo = getSensorInformation(scene)
        except (EEException):
#             logging.error("Google Earth Engine Services Error: " + str(sys.exc_info()))
            return "Google Earth Engine Services Error: " + str(sys.exc_info())
    return getSceneImage(scene, sensorinfo, region, width, height, layerParameters)

def getSceneImage(scene, sensorinfo, region, width, height, layerParameters):
    try:
        # SET THE DEFAULT PARAMETER VALUES
        layerParameters.setdefault("min", 0)
        layerParameters.setdefault("max", 0.7)
        layerParameters.setdefault("redBand", sensorinfo['bands']['Red'])
        layerParameters.setdefault("greenBand", sensorinfo['bands']['Green'])
        layerParameters.setdefault("blueBand", sensorinfo['bands']['Blue'])
        layerParameters.setdefault("removeEdges", 0)
        # SET THE BANDS FOR IMAGE RENDERING
        bands = layerParameters['redBand'] + "," + layerParameters['greenBand'] + "," + layerParameters['blueBand'] 
        # APPLY CORRECTIONS IF SPECIFIED
        # 1. ILLUMINATION CORRECTION
        layerParameters.setdefault("illuminationCorrection", False)
        if layerParameters['illuminationCorrection']:
            scene = illuminationCorrection(scene)  # will only return bands 4,3,2
        # 2. CLOUD REMOVAL 
        layerParameters.setdefault("cloudCorrection", False)
        # APPLY HSV IF SPECIFIED
        layerParameters.setdefault("hsv", False)
        defaulthsvbands = getGEEBandNames("SWIR2,NIR,Red", sensorinfo)
        layerParameters.setdefault("hsvbands", defaulthsvbands)
        if layerParameters['removeEdges']!=0:
            scene = scene.clip(scene.geometry().buffer(layerParameters['removeEdges'])) #remove the edges on L5 or L7
        if layerParameters['hsv']:
            scene = convertToHsv(scene, layerParameters["hsvbands"])  # will only return bands 7,5,4 in Landsat 8
            output_thumbnail = scene.getThumbUrl({'bands': 'h,s,v', 'dimensions': width + 'x' + height , 'region': region, 'gain':'0.8,300,0.01', })
            return output_thumbnail
        # FINAL STEP IS THE DETECTION PROCESS IF ANY
        if 'detectExpression' in layerParameters.keys():
            if "b('hue')" in layerParameters['detectExpression']:
                detectionInput = convertToHsv(scene, layerParameters["hsvbands"])  # convert to hsv
            else:
                detectionInput = scene
            booleanClass = detectionInput.expression(layerParameters['detectExpression'])  # detect the class
            mask = scene.mask(booleanClass)  # create the mask
            output_thumbnail = mask.getThumbUrl({'bands': bands, 'dimensions': width + 'x' + height , 'min': layerParameters['min'], 'max': layerParameters['max'], 'region': region})
            return output_thumbnail
        if 'detectWater' in layerParameters.keys():
            if layerParameters['detectWater']:
                detection = detectWater(scene, sensorinfo)
                output_thumbnail = detection.getThumbUrl({'palette': '444444,000000,ffffff,0000ff', 'dimensions': width + 'x' + height , 'min': 0, 'max': 3, 'region': region})
                return output_thumbnail
        output_thumbnail = scene.getThumbUrl({'bands': bands, 'dimensions': width + 'x' + height , 'min': layerParameters['min'], 'max': layerParameters['max'], 'region': region})
        return output_thumbnail
    
    except (EEException):
        return "Google Earth Engine Error: " + str(sys.exc_info())        

def illuminationCorrection(image):
    # accepts either a single scene which will have the sun elevation and azimuth already populated, or a collection image which will need to have the sun elevation and azimuth manually populated and accessed via the properties
    try:
        terrain = ee.call('Terrain', ee.Image('srtm90_v4'))
        solar_zenith = (90 - image.getInfo()['properties']['SUN_ELEVATION'])
#             solar_zenith = 31.627850000000002
        solar_azimuth = image.getInfo()['properties']['SUN_AZIMUTH']
#             solar_azimuth = 50.377735
        solar_zenith_radians = (solar_zenith * math.pi) / 180
        slope_radians = terrain.select(['slope']).expression("(b('slope')*" + str(math.pi) + ")/180")
        aspect = terrain.select(['aspect'])
        cosZ = math.cos(solar_zenith_radians)
        cosS = slope_radians.cos()
        slope_illumination = cosS.expression("b('slope')*(" + str(cosZ) + ")").select(['slope'], ['b1'])
        sinZ = math.sin(solar_zenith_radians)
        sinS = slope_radians.sin()
        azimuth_diff_radians = aspect.expression("((b('aspect')-" + str(solar_azimuth) + ")*" + str(math.pi) + ")/180")
        cosPhi = azimuth_diff_radians.cos()
        aspect_illumination = cosPhi.multiply(sinS).expression("b('aspect')*" + str(sinZ)).select(['aspect'], ['b1'])
        ic = slope_illumination.add(aspect_illumination)
        return image.expression("((image * (cosZ + coeff)) / (ic + coeff)) + offsets", {'image': image.select('B4', 'B3', 'B2'), 'ic': ic, 'cosZ': cosZ, 'coeff': [12, 9, 25], 'offsets': [0, 0, 0]})

    except (EEException):
        return "Google Earth Engine Error: " + str(sys.exc_info())        

def rgbToHsv(image):
    return image.select(["r","g","b"]).rgbToHsv().multiply(ee.Image([360, 1, 1]))

def convertToHsv(image, bands):
    try:
        bandsArray = bands.split(",")
        r = bandsArray[0]
        g = bandsArray[1]
        b = bandsArray[2]
        img = ee.Image.cat([image.select([r], ['r']), image.select([g], ['g']), image.select([b], ['b'])])
        return rgbToHsv(img)

    except (EEException):
        return "Google Earth Engine Error: " + str(sys.exc_info())        

def getDatesForBB(ll_x, ll_y, ur_x, ur_y, crs):
    try:
        authenticate()
        bbox_latlong = getBoundingBoxLL(ll_x, ll_y, ur_x, ur_y, crs)  # [[114, 6], [114, 5], [115, 5], [115, 6]]
        clip_polygon = ee.Feature.Polygon([bbox_latlong])
        return ee.ImageCollection("LANDSAT/LC8_L1T").filterBounds(clip_polygon).aggregate_array("DATE_ACQUIRED").getInfo()

    except (EEException):
        return "Google Earth Engine Error: " + str(sys.exc_info())        

def getDatesForPoint(x, y, crs):
    try:
        authenticate()
        lng, lat = utilities.getPointLL(x, y, crs)
        point = ee.Geometry.Point([lng,lat])
        stringDates = ee.ImageCollection("LANDSAT/LC8_L1T").filterBounds(point).aggregate_array("DATE_ACQUIRED").getInfo()  # get the dates as strings
        dates = [dateToDateTime(s) for s in stringDates]
        return [s.isoformat() for s in sorted(set(dates))]  # convert them to properly formatted strings 

    except (EEException):
        return "Google Earth Engine Error: " + str(sys.exc_info())        
        
def getScenesForPoint(collection, x, y, crs):  
    try:
        authenticate()
        lng, lat = utilities.getPointLL(x, y, crs)
        point = ee.Geometry.Point([lng,lat])
        scenes = ee.ImageCollection(collection).filterBounds(point).getInfo()
        #Weird error when you try to load L5 -  "ImageCollection.load: ImageCollection asset 'LANDSAT/L5_L1T' not found at version 1425084354300000.\" even if you pass in LANDSAT/L5_L1TOA!
        # Landsat image ids are LANDSAT/LC8_L1T/LC81970502014029LGN00 whereas Landsat TOA are LC8_L1T_TOA/LC81970502014029LGN00 without the Landsat - so add this in
        if collection[-3:] == "TOA":
            for scene in scenes['features']:
                scene['id'] = scene['id']
        return scenes

    except (EEException):
        return "Google Earth Engine Error: " + str(sys.exc_info())        

def getScenesForPointShort(collection, x, y, crs):  
    try:
        authenticate()
        lng, lat = utilities.getPointLL(x, y, crs)
        point = ee.Geometry.Point([lng,lat])
        features = ee.ImageCollection(collection).filterBounds(point).getInfo()["features"]
        return [(f["properties"]["LANDSAT_SCENE_ID"],f["properties"]["DATE_ACQUIRED"],f["properties"]["CLOUD_COVER"]) for f in features]

    except (EEException):
        return "Google Earth Engine Error: " + str(sys.exc_info())        


def getValuesForPoint(sceneid, x, y, crs):
    try:
        authenticate()
        lng, lat = utilities.getPointLL(x, y, crs)
        scene = ee.Image(sceneid)
        collection = ee.ImageCollection(scene)
        data = collection.getRegion(ee.Geometry.Point(lng, lat), 30).getInfo()
        if len(data) == 1:
            raise GoogleEarthEngineError("No values for point x:" + str(x) + " y: " + str(y) + " for sceneid: " + sceneid)
        return OrderedDict([(data[0][i], data[1][i]) for i in range (len(data[0]))])
    
    except (EEException, GoogleEarthEngineError):
        return "Google Earth Engine Error: " + str(sys.exc_info())        

def getValuesForPoints(sceneid, pointsArray):  # points are as a [[117.49949,5.50077],[117.50005,5.50074]]
    try:
        authenticate()
        multipoint = ee.Geometry.MultiPoint(pointsArray)
        scene = ee.Image(sceneid)
        collection = ee.ImageCollection(scene)
        data = collection.getRegion(multipoint, 30).getInfo()
        return data
    
    except (EEException, GoogleEarthEngineError):
        return "Google Earth Engine Error: " + str(sys.exc_info())        

def getBoundingBoxLL(ll_x, ll_y, ur_x, ur_y, crs):  # gets a lat/long bounding box suitable for sending to the Google Earth Engine API
        ll_long, ll_lat = utilities.getPointLL(ll_x, ll_y, crs)  # transform the data to lat/long so that we can use it in Google Earth Engine
        ur_long, ur_lat = utilities.getPointLL(ur_x, ur_y, crs)
        return [[ll_long, ur_lat], [ll_long, ll_lat], [ur_long, ll_lat], [ur_long, ur_lat]]  # get the area of interest

def getDateTimeForScene(sceneid):
    try:
        authenticate()
        scene = ee.Image(sceneid)
        return scene.getInfo()['properties']['DATE_ACQUIRED'] + ' ' + scene.getInfo()['properties']['SCENE_CENTER_TIME'][:8]
    
    except (EEException, GoogleEarthEngineError):
        return "Google Earth Engine Error: " + str(sys.exc_info())        

def dateToDateTime(_date):  # converts a Google date into a Python datetime, e.g. 2013-06-14 to datetime.datetime(2013, 5, 2, 0, 0))
    d = _date.split("-")
    return datetime.datetime(int(d[0]), int(d[1]), int(d[2]))

def landsatNDVI(img):
    return img.normalizedDifference(["B5","B4"])

def detectWater(image, sensor=None, applyCloudMask=True, applySnowMask=True, applySlopeMask=False, applyNDVIMask=False, applyTemperatureMask=False, applyBareRockMask=False):
    # get the sensor information from the scene if it isnt already known
    if not sensor:
        try:
            sensor = getSensorInformation(image)
        except (GoogleEarthEngineError) as e:
            sensor = sensors[2]  # use landsat 8 as the default value if you cant get the sensor information
            print e
    sunElevationThreshold = 35               #Landsat scenes with a solar elevation angle greater than this angle will be included - not currently used
    lowerSceneTempThreshold = 264            #lower temperature threshold for the scene (default value:262)
    upperSceneTempThreshold = 310            #upper temperature threshold for the scene (default value:310)
    cloudMaxTemperature = 299                #when putting clouds back in, only pixels < this value will be considered clouds
    cloudAndWater = "((b('hue')<(0.41364045204877986*b('Blue'))+241.58503770843737)&&(b('hue')>(-11159.99999999992*b('Blue'))+706.602272727269)&&(b('hue')>(6.608688285703755*b('Blue'))+192.68448650503294))||((b('hue')<(6.608688285703755*b('Blue'))+192.68448650503294)&&(b('hue')>(-1185.0000000000016*b('Blue'))+247.52556818181824)&&(b('hue')>(10.590659688301406*b('Blue'))+161.25283307931002))||((b('hue')<(-2880.000000000025*b('Blue'))+22978.102736040695)&&(b('hue')<(10.590659688301406*b('Blue'))+161.25283307931002)&&(b('hue')>(-8.242805824080952*b('Blue'))+162.61183882935126))||((b('hue')>(-2.390925916467925*b('Blue'))+116.11991638044418)&&(b('hue')<(-8.242805824080952*b('Blue'))+162.61183882935126)&&(b('hue')>(-474.7757035969288*b('Blue'))+196.2764286118238))||((b('hue')>(-1.6963273991013927*b('Blue'))+110.6014811233367)&&(b('hue')<(-2.390925916467925*b('Blue'))+116.11991638044418)&&(b('hue')>(-22.581644771334126*b('Blue'))+119.5459742877233))||((b('hue')<(-22.581644771334126*b('Blue'))+119.5459742877233)&&(b('hue')>(-52.75862068965494*b('Blue'))+124.66654813682212)&&(b('hue')>(5.205078970337692*b('Blue'))+107.64583620801584))||((b('hue')<(-52.75862068965494*b('Blue'))+124.66654813682212)&&(b('hue')>(-118.032786885246*b('Blue'))+135.7425813797672)&&(b('hue')>(19.636363636364297*b('Blue'))+103.40817124694752))"
    water1 = "b('value')<0.62&&(((b('hue')<((-9.867784585617413*b('nd'))+238.26034242940045))&&(b('hue')>((-12960.000000000335*b('nd'))-12714.048607819708))&&(b('hue')>((23.627546071775214*b('nd'))+255.53176874753507)))||((b('hue')<((-54.685799109352004*b('nd'))+215.15052322834936))&&(b('hue')<((23.627546071775214*b('nd'))+255.53176874753507))&&(b('hue')>((-7.321079389910027*b('nd'))+224.6166270396205)))||((b('hue')<((-172.0408163265306*b('nd'))+191.69646750224035))&&(b('hue')<((-7.321079389910027*b('nd'))+224.6166270396205))&&(b('hue')>((-38.11764705882351*b('nd'))+193.8533786110101)))||((b('hue')>((-52.06378986866776*b('nd'))+179.92232432949075))&&(b('hue')<((-879.6226415094455*b('nd'))+180.3004476242325))&&(b('hue')<((-38.11764705882351*b('nd'))+193.8533786110101))))"
    water2 = "b('value')<0.62&&(((b('hue')<((-119.15098406819945*b('nd'))+180.0533162435398))&&(b('hue')>((-994.2857142867327*b('nd'))+180.04805813312743))&&(b('hue')>((-116.5000234173271*b('nd'))+179.9633248496054)))||((b('hue')<((-2368.4258422651174*b('nd'))+256.40879883589054))&&(b('hue')<((-116.5000234173271*b('nd'))+179.9633248496054))&&(b('hue')>((-267.6720052547653*b('nd'))+179.97791758964533)))||((b('hue')<((-108.07947019867622*b('nd'))+179.67747476669464))&&(b('hue')>((-2368.4258422651174*b('nd'))+256.40879883589054))&&(b('hue')>((58.99660016815455*b('nd'))+168.09286521078695)))||((b('hue')<((-104.45621862799788*b('nd'))+179.4262481567021))&&(b('hue')<((58.99660016815455*b('nd'))+168.09286521078695))&&(b('hue')>((-52.1565190088889*b('nd'))+172.13690440390852)))||((b('hue')<((-52.1565190088889*b('nd'))+172.13690440390852))&&(b('hue')>((-204.2258047185466*b('nd'))+177.66958001421082))&&(b('hue')>((37.74894387447151*b('nd'))+159.60620482085795))))"
    water3 = "b('SWIR1')<0||b('SWIR2')<0"
    confusion1a = "(((b('hue')<((-49.74358974358937*b('nd'))+196.13881379789424))&&(b('hue')>((-388.2352941176396*b('nd'))+71.02910650151634))&&(b('hue')>((-23.22580645161292*b('nd'))+203.03136575198846)))||((b('hue')<((-77.40259740259752*b('nd'))+188.94963266652547))&&(b('hue')<((-23.22580645161292*b('nd'))+203.03136575198846))&&(b('hue')>((-51.16071428571436*b('nd'))+192.92896822354658)))||((b('hue')>((-66.84871654833425*b('nd'))+187.2555492802913))&&(b('hue')<((-110.14373716632423*b('nd'))+183.9847457695416))&&(b('hue')<((-51.16071428571436*b('nd'))+192.92896822354658)))||((b('hue')<((-66.84871654833425*b('nd'))+187.2555492802913))&&(b('hue')>((-90.93264248704664*b('nd'))+178.5458232513616))&&(b('hue')<((-181.85567010309282*b('nd'))+178.56713333595917)))||((b('hue')>((-181.85567010309282*b('nd'))+178.56713333595917))&&(b('hue')<((-5040.000000000369*b('nd'))+179.70576091328076))&&(b('hue')<((-151.6182572614111*b('nd'))+180.85147538423308))))"
    confusion1b = "(((b('saturation')<((-2.043478260869566*b('Blue'))+1.4876934851282484))&&(b('saturation')<((-0.012289780077619696*b('Blue'))+0.9967606071389642))&&(b('saturation')>((-0.09907120743034059*b('Blue'))+0.9967723098208588)))||((b('saturation')>((2.095477386934673*b('Blue'))+0.4426957478637016))&&(b('saturation')<((-0.09907120743034059*b('Blue'))+0.9967723098208588))&&(b('saturation')>((-13.86936936936928*b('Blue'))+0.9986292672816813)))||((b('saturation')<((2.095477386934673*b('Blue'))+0.4426957478637016))&&(b('saturation')>((-0.45195729537366536*b('Blue'))+0.5314034160324479))&&(b('saturation')>((12.739776951672882*b('Blue'))-2.2447621295403355))))"
    confusion2a = "(((b('hue')<((-323.2653061224475*b('nd'))+183.40185793495874))&&(b('hue')<((158.07495741056292*b('nd'))+215.95099454586804))&&(b('hue')>((-19.45161290322491*b('nd'))+195.80505541813127)))||((b('hue')<((-19.45161290322491*b('nd'))+195.80505541813127))&&(b('hue')>((-114.87179487179472*b('nd'))+184.97665280719505))&&(b('hue')>((38.393782383421026*b('nd'))+198.16659433900784)))||((b('hue')<((-360.00000000000256*b('nd'))+181.9021636393549))&&(b('hue')<((38.393782383421026*b('nd'))+198.16659433900784))&&(b('hue')>((-43.145604395603854*b('nd'))+191.14936474697558)))||((b('hue')<((-43.145604395603854*b('nd'))+191.14936474697558))&&(b('hue')>((-158.76923076923046*b('nd'))+181.19886641019133))&&(b('hue')>((429.86013986014024*b('nd'))+204.95374714744474)))||((b('hue')<((-398.29787234042374*b('nd'))+180.784463735428))&&(b('hue')<((429.86013986014024*b('nd'))+204.95374714744474))&&(b('hue')>((18.69718309859311*b('nd'))+188.36074739446966)))||((b('hue')<((-2132.068965517284*b('nd'))+149.28399045541414))&&(b('hue')<((18.69718309859311*b('nd'))+188.36074739446966))&&(b('hue')>((-180.57507987220498*b('nd'))+180.31886386417185)))||((b('hue')<((-401.15384615384954*b('nd'))+180.73257422870344))&&(b('hue')>((-2132.068965517284*b('nd'))+149.28399045541414))&&(b('hue')>((-156.29268292682937*b('nd'))+180.705030134435)))||((b('hue')<((-4859.999999999733*b('nd'))+181.23414367798406))&&(b('hue')<((-156.29268292682937*b('nd'))+180.705030134435))&&(b('hue')>((-201.73913043478356*b('nd'))+179.98228908171535))))"
    confusion2b = "(((b('SWIR2')<((-0.323042168674698*b('Blue'))+0.06801551910768028))&&(b('SWIR2')<((0.5604681404421293*b('Blue'))-0.026340620936280618))&&(b('SWIR2')>((0.0009537434430138915*b('Blue'))-0.00020080770147852338)))||((b('SWIR2')<((-0.49875724937862376*b('Blue'))+0.10501178024026461))&&(b('SWIR2')<((1.4297520661157026*b('Blue'))-0.11917742768595024))&&(b('SWIR2')>((-0.323042168674698*b('Blue'))+0.06801551910768028)))||((b('SWIR2')<((-0.7169373549883978*b('Blue'))+0.1509489196635725))&&(b('SWIR2')<((1.3166023166023175*b('Blue'))-0.10602376930501928))&&(b('SWIR2')>((-0.49875724937862376*b('Blue'))+0.10501178024026461)))||((b('SWIR2')>((8.135802469135795*b('Blue'))-1.7129677854938241))&&(b('SWIR2')<((-0.09797151488994237*b('Blue'))+0.07273194729175612))&&(b('SWIR2')>((-0.7169373549883978*b('Blue'))+0.1509489196635725)))||((b('SWIR2')<((-0.3973412112259951*b('Blue'))+0.1376577501846375))&&(b('SWIR2')<((2.0279720279720297*b('Blue'))-0.19591755900349633))&&(b('SWIR2')>((-0.09797151488994237*b('Blue'))+0.07273194729175612)))||((b('SWIR2')<((-0.9340727048675277*b('Blue'))+0.2540613928681448))&&(b('SWIR2')<((1.7377450980392386*b('Blue'))-0.15600001914828718))&&(b('SWIR2')>((-0.3973412112259951*b('Blue'))+0.1376577501846375)))||((b('SWIR2')<((0.5585585585585591*b('Blue'))+0.024977477477477597))&&(b('SWIR2')>((-0.9340727048675277*b('Blue'))+0.2540613928681448))&&(b('SWIR2')>((16.392156862745423*b('Blue'))-3.503564644607911)))||((b('SWIR2')>((2.1705685618729085*b('Blue'))-0.4192576818561867))&&(b('SWIR2')<((0.08437200383509218*b('Blue'))+0.1306506921140938))&&(b('SWIR2')<((16.392156862745423*b('Blue'))-3.503564644607911)))||((b('SWIR2')>((0.5275310834813499*b('Blue'))-0.06292392873001777))&&(b('SWIR2')<((-1.3333333333333348*b('Blue'))+0.5043489583333338))&&(b('SWIR2')<((2.1705685618729085*b('Blue'))-0.4192576818561867))))"
    confusion2c = "(((b('value532')<((-3.0133928571428577*b('SWIR2'))+0.7676348612804655))&&(b('value532')<((-0.2571428571428576*b('SWIR2'))+0.4733992419470712))&&(b('value532')>((-1.3327526132404202*b('SWIR2'))+0.47057808119912775)))||((b('value532')>((1.0686619718309858*b('SWIR2'))+0.04612288510953274))&&(b('value532')<((-1.3327526132404202*b('SWIR2'))+0.4705780811991277))&&(b('value532')>((-228.66666666671583*b('SWIR2'))-0.12568418898601724))))"
    confusion2d = "(b('hue532')>238)"
    confusion3a = "(((b('saturation')<((-2.2326203208556143*b('value'))+1.5257678652540891))&&(b('saturation')<((-0.00534759358288754*b('value'))+0.9973687549803982))&&(b('saturation')>((-0.7477718360071299*b('value'))+0.9999601250716116)))||((b('saturation')>((0.7335092348284965*b('value'))+0.4754156611894009))&&(b('saturation')<((-0.7397078353253644*b('value'))+1.1715886848550134))&&(b('saturation')>((-2.2326203208556143*b('value'))+1.5257678652540891)))||((b('saturation')<((-16.484848484848392*b('value'))+8.612000825120266))&&(b('saturation')<((-0.018055555555555623*b('value'))+1.0003835971762043))&&(b('saturation')>((-0.7397078353253644*b('value'))+1.1715886848550134)))||((b('saturation')>((1.545243619489559*b('value'))+0.18796800118751184))&&(b('saturation')<((-0.7477718360071299*b('value'))+0.9999601250716116))&&(b('saturation')>((-2.178002894356006*b('value'))+1.004952227667868)))||((b('saturation')>((0.4907407407407418*b('value'))+0.41935537119167954))&&(b('saturation')<((-2.178002894356006*b('value'))+1.0049522276678682))&&(b('saturation')>((-42.39534883720828*b('value'))+1.1453275299128312)))||((b('saturation')>((1.8633540372670816*b('value'))+0.11816569488389755))&&(b('saturation')<((0.4907407407407418*b('value'))+0.41935537119167954))&&(b('saturation')>((0.03696098562628343*b('value'))+0.4270369171578985))))"
    confusion3b = "(((b('value532')<((-8.999999999999996*b('SWIR2'))+1.1836428258302192))&&(b('value532')<((-0.25605798072220454*b('SWIR2'))+0.4734020874128705))&&(b('value532')>((-1.567464014026764*b('SWIR2'))+0.46996246890364646)))||((b('value532')<((-1.567464014026764*b('SWIR2'))+0.46996246890364646))&&(b('value532')>((-2.378156296376779*b('SWIR2'))+0.46783614638503673))&&(b('value532')>((42.666666666666465*b('SWIR2'))-3.77744786750256)))||((b('value532')>((2.0883643769837543*b('SWIR2'))+0.046885467371981064))&&(b('value532')<((-2.378156296376779*b('SWIR2'))+0.4678361463850367))&&(b('value532')>((-228.66666666671583*b('SWIR2'))-0.12568418898601724)))||((b('value532')<((-4.78571428571428*b('SWIR2'))+0.6947383023337331))&&(b('value532')<((2.0883643769837543*b('SWIR2'))+0.04688546737198104))&&(b('value532')>((1.0673991822800284*b('SWIR2'))+0.04612194073506829))))"
    confusion4a = "(((b('hue')<((-171.9402985074626*b('value'))+284.156529850746))&&(b('hue')<((26.190476190476137*b('value'))+177.22782738095222))&&(b('hue')>((-15.423197492163006*b('value'))+180.02374608150456)))||((b('hue')<((-15.423197492163006*b('value'))+180.02374608150456))&&(b('hue')>((-787.6056338028174*b('value'))+231.90475352112665))&&(b('hue')>((205.6451612903227*b('value'))+32.944203629032074)))||((b('hue')<((205.6451612903227*b('value'))+32.944203629032074))&&(b('hue')>((-13.36870026525184*b('value'))+76.81541777188309))&&(b('hue')>((430.62670299727523*b('value'))-116.73882833787471))))"
    confusion4b = "(((b('nd')<((-0.4006259780907667*b('value'))+0.25238142590835944))&&(b('nd')<((2.6183213726200956*b('value'))-0.14069421605734192))&&(b('nd')>((0.04660702286934955*b('value'))-0.016930462975588336)))||((b('nd')<((-5.639344262295089*b('value'))+3.4069990713440506))&&(b('nd')<((0.04660702286934955*b('value'))-0.01693046297558834))&&(b('nd')>((-0.1755502266736536*b('value'))-0.0062391453413314))))"
    confusion5a = "(((b('hue')<((-41.390273937152394*b('nd'))+199.35367359600045))&&(b('hue')<((980.036035727654*b('nd'))+640.801356804259))&&(b('hue')>((321.2575972304732*b('nd'))+340.18915447676704)))||((b('hue')<((-65.8789625360229*b('nd'))+189.84341168861118))&&(b('hue')<((321.2575972304732*b('nd'))+340.18915447676704))&&(b('hue')>((79.91668325971264*b('nd'))+230.0610455089285)))||((b('hue')<((-79.35871743486943*b('nd'))+186.12503008982895))&&(b('hue')<((79.91668325971264*b('nd'))+230.0610455089285))&&(b('hue')>((15.881427495031524*b('nd'))+200.84063066666678)))||((b('hue')<((-100.08620689655164*b('nd'))+182.9224157290126))&&(b('hue')<((15.881427495031524*b('nd'))+200.84063066666678))&&(b('hue')>((-7.254757545361759*b('nd'))+190.28318201319394)))||((b('hue')<((-124.615384615385*b('nd'))+180.97745477457968))&&(b('hue')<((-7.254757545361759*b('nd'))+190.28318201319394))&&(b('hue')>((-19.055497384172963*b('nd'))+184.89829661814167)))||((b('hue')>((-25.873050054257675*b('nd'))+181.7873272802364))&&(b('hue')<((-140.7166123778528*b('nd'))+180.37940215061724))&&(b('hue')<((-19.055497384172963*b('nd'))+184.89829661814167)))||((b('hue')>((-30.31391870513669*b('nd'))+179.76088071280893))&&(b('hue')<((-187.17066924733743*b('nd'))+179.80989844735336))&&(b('hue')<((-25.873050054257675*b('nd'))+181.7873272802364)))||((b('hue')<((-155.73667711598745*b('nd'))+180.19526360453366))&&(b('hue')>((-187.17066924733743*b('nd'))+179.80989844735336))&&(b('hue')>((953.6618512259481*b('nd'))+179.45338828470543)))||((b('hue')>((47.569422700668035*b('nd'))+179.7365421686196))&&(b('hue')<((31.592769201982623*b('nd'))+180.0699929381771))&&(b('hue')<((953.6618512259481*b('nd'))+179.45338828470543)))||((b('hue')>((31.592769201982623*b('nd'))+180.0699929381771))&&(b('hue')<((-102.42677824267734*b('nd'))+182.86713197826745))&&(b('hue')<((3158.312807223996*b('nd'))+177.97909740428108)))||((b('hue')>((-113.32329793300876*b('nd'))+179.78682114381763))&&(b('hue')<((-318.39195979899586*b('nd'))+187.37456878244578))&&(b('hue')<((47.569422700668035*b('nd'))+179.7365421686196)))||((b('hue')<((-113.32329793300876*b('nd'))+179.78682114381763))&&(b('hue')>((-142.88372093023278*b('nd'))+179.79605877600426))&&(b('hue')<((-159.8049491628185*b('nd'))+181.50668919264223)))||((b('hue')>((1080.0000000000098*b('nd'))+56.170157613212425))&&(b('hue')<((-120.30147453115049*b('nd'))+180.0450207269362))&&(b('hue')>((-159.8049491628185*b('nd'))+181.50668919264223)))||((b('hue')<((-30.31391870513669*b('nd'))+179.76088071280893))&&(b('hue')>((-55.18624641833813*b('nd'))+168.4111995849124))&&(b('hue')>((2769.534803268574*b('nd'))+178.88592798719202))))"
    confusion5b = "(((b('TIR')<((-37.4607329842932*b('SWIR1'))+270.5710658903785))&&(b('TIR')<((3873.750000000057*b('SWIR1'))+289.8215562167857))&&(b('TIR')>((42.76923076923073*b('SWIR1'))+213.50123620476631)))||((b('TIR')<((-1.6063348416289716*b('SWIR1'))+270.74753675623697))&&(b('TIR')>((-37.4607329842932*b('SWIR1'))+270.5710658903785))&&(b('TIR')>((226.66666666666728*b('SWIR1'))+82.6898179355349)))||((b('TIR')<((-1.7241379310344813*b('SWIR1'))+270.8445862545011))&&(b('TIR')<((5.714285714284849*b('SWIR1'))+270.7835679355356))&&(b('TIR')>((-1.6063348416289716*b('SWIR1'))+270.74753675623697)))||((b('TIR')<((-15.871404399323138*b('SWIR1'))+282.49950226294675))&&(b('TIR')<((28.243727598566267*b('SWIR1'))+270.5987561075786))&&(b('TIR')>((-1.7241379310344813*b('SWIR1'))+270.8445862545011)))||((b('TIR')<((-14.764776839565704*b('SWIR1'))+282.2009721876465))&&(b('TIR')<((4484.999999999887*b('SWIR1'))+234.03942731053635))&&(b('TIR')>((28.243727598566267*b('SWIR1'))+270.5987561075786))))"
    confusion5c = "(((b('Blue')>((4.8417656150246735*b('saturation'))-2.1345948555473897))&&(b('Blue')<((0.1372549019607847*b('saturation'))+2.541367543066504))&&(b('Blue')<((65.27916047754636*b('saturation'))-44.97113295340387)))||((b('Blue')>((8.084344025406292*b('saturation'))-5.357496374168239))&&(b('Blue')<((4.8417656150246735*b('saturation'))-2.1345948555473897))&&(b('Blue')>((-2.0288015770823886*b('saturation'))+2.7350940836938467)))||((b('Blue')<((-109.79419385952704*b('saturation'))+111.80572088090663))&&(b('Blue')<((8.084344025406292*b('saturation'))-5.357496374168237))&&(b('Blue')>((-4.3978728050230655*b('saturation'))+4.630836908607832)))||((b('Blue')<((-4.3978728050230655*b('saturation'))+4.630836908607832))&&(b('Blue')>((-6.7287331975861875*b('saturation'))+6.496003229047556))&&(b('Blue')>((-1.662267492121429*b('saturation'))+1.8490682560509786)))||((b('Blue')>((-2.290356886887485*b('saturation'))+2.425148455618598))&&(b('Blue')<((-6.7287331975861875*b('saturation'))+6.496003229047557))&&(b('Blue')>((-499.2108270862114*b('saturation'))+400.5826752028271)))||((b('Blue')<((-2.290356886887485*b('saturation'))+2.425148455618598))&&(b('Blue')>((-2.6721311475409864*b('saturation'))+2.7310450819672165))&&(b('Blue')>((-1.557000478788249*b('saturation'))+1.7525179201366887)))||((b('Blue')<((-1.662267492121429*b('saturation'))+1.8490682560509786))&&(b('Blue')>((-4.648304510366765*b('saturation'))+4.58784527684082))&&(b('Blue')>((0.22760258599122304*b('saturation'))-0.07269337962982575))))"
    confusion6 = "b('TIR')>" + str(lowerSceneTempThreshold) + "&&b('TIR')<" + str(upperSceneTempThreshold)
    validObservation = "(((b('TIR')<((0.21276595744678117*b('saturation'))+420.8908397964015))&&(b('TIR')>((-15191.999999997235*b('saturation'))-125.68949770908034))&&(b('TIR')>((84.85848005348791*b('saturation'))+300.09814355274244)))||((b('TIR')>((116.36848715640691*b('saturation'))+255.13214902761092))&&(b('TIR')<((84.85848005348791*b('saturation'))+300.09814355274244))&&(b('TIR')>((-1.3488098389876424*b('saturation'))+297.69542452050007)))||((b('TIR')<((116.36848715640691*b('saturation'))+255.1321490276109))&&(b('TIR')>((-4.782608695652049*b('saturation'))+298.936989952716))&&(b('TIR')>((177.66748694362772*b('saturation'))+167.6561138802603)))||((b('TIR')<((177.66748694362772*b('saturation'))+167.6561138802603))&&(b('TIR')>((-20.224719101123455*b('saturation'))+310.0482682194368))&&(b('TIR')>((273.5211550475191*b('saturation'))+30.869235315130652)))||((b('TIR')>((-153.9042175535099*b('saturation'))+437.0986079228801))&&(b('TIR')>((324.24657534246626*b('saturation'))-41.517894393142))&&(b('TIR')<((273.5211550475191*b('saturation'))+30.869235315130652)))||((b('TIR')<((-153.9042175535099*b('saturation'))+437.0986079228801))&&(b('TIR')>((-1590.239504725967*b('saturation'))+1802.2061096412613))&&(b('TIR')>((-1.7021276595748691*b('saturation'))+284.748276202167)))||((b('TIR')<((-1.3488098389876424*b('saturation'))+297.69542452050007))&&(b('TIR')>((-2.033898305084576*b('saturation'))+297.6763301365064))&&(b('TIR')>((-0.8058993571458792*b('saturation'))+297.4991233056708))))"
    missingDataExpression = "b('Blue')<0&&b('Green')<0&&b('Red')<0&&b('NIR')<0&&b('SWIR1')<0&&b('SWIR2')<0&&b('TIR')<0"
    image = image.select(sensor['bands'].values(),sensor['bands'].keys())
    #STATIC MASKS START
    fc = ee.FeatureCollection('ft:1_WsaRS8TGo_IxtVEXFoZI0gKE1wZwAsEAHTNPAP8')
    static_urban = ee.Image().byte().paint(fc).mask()
    #STATIC MASKS END
    if not (sensor['name']=='LANDSAT_8'):
      image = image.clip(image.geometry().buffer(-6000)) #remove the edges on L5 or L7
    #compute the ndvi
    image = image.addBands(image.normalizedDifference(["NIR","Red"]))
    #compute the hsv for 754
    image = image.addBands(image.select(["SWIR2","NIR","Red"]).rgbToHsv().multiply(ee.Image([360, 1, 1])))
    #compute the hsv for 532
    image = image.addBands(image.select(["NIR","Green","Blue"]).rgbToHsv().select([0,1,2],["hue532","saturation532","value532"]).multiply(ee.Image([360, 1, 1])))
    
    #get the cloud/water class
    image = image.addBands(image.expression(cloudAndWater).select([0],["cloudAndWater"]))
    
    #get the detected water
    #first in non-urban areas using our classifier
    image = image.addBands(image.expression(water1).select([0],["water1"])) #water where ndvi<0
    image = image.addBands(image.expression(water2).select([0],["water2"])) #water where ndvi>0
    image = image.addBands(image.select(["water.*"]).reduce(ee.Reducer.anyNonZero()).multiply(ee.call('Image.not',static_urban)).select([0],["waterNotUrban"]))
    #then detect water in urban areas using Noels classifier
    classifier = ee.Image("JTBVBU2GPFLO2MKAVD3RHQBG") # this is Noels improved classifier
    image = image.addBands(image.select([0,1,2,3,4,5,6]).classify(classifier).multiply(static_urban).select([0],["waterUrban"]))
    #get the overall water detection
    image = image.addBands(image.select(["waterNotUrban","waterUrban"]).reduce(ee.Reducer.anyNonZero()).multiply(2).select([0],["water"])) #water is class 2
    
    #get the confusion pixels for confusion1
    image = image.addBands(image.expression(confusion1a).select([0],["conf1a"]))
    image = image.addBands(ee.call('Image.not',image.expression(confusion1b)).select([0],["conf1b"]))
    image = image.addBands(image.select(["conf1.*"]).reduce(ee.Reducer.allNonZero()).select([0],["confusion1"]))
    
    #get the confusion pixels for confusion2
    image = image.addBands(image.expression(confusion2a).select([0],["conf2a"]))
    image = image.addBands(ee.call('Image.not',image.expression(confusion2b)).select([0],["conf2b"]))
    image = image.addBands(ee.call('Image.not',image.expression(confusion2c)).select([0],["conf2c"]))
    image = image.addBands(image.expression(confusion2d).select([0],["conf2d"]))
    image = image.addBands(image.select(["conf2.*"]).reduce(ee.Reducer.allNonZero()).select([0],["confusion2"]))
    
    #get the confusion pixels for confusion3
    image = image.addBands(ee.call('Image.not',image.expression(confusion3a)).select([0],["conf3a"]))
    image = image.addBands(ee.call('Image.not',image.expression(confusion3b)).select([0],["conf3b"]))
    image = image.addBands(image.expression("b('water2')").select([0],["conf3c"]))
    image = image.addBands(image.select(["conf3.*"]).reduce(ee.Reducer.allNonZero()).select([0],["confusion3"]))
    
    #get the confusion pixels for confusion4 - bright soil around Aral Sea
    image = image.addBands(image.expression(confusion4a).select([0],["conf4a"]))
    image = image.addBands(image.expression(confusion4b).select([0],["conf4b"]))
    image = image.addBands(image.select(["conf4.*"]).reduce(ee.Reducer.allNonZero()).select([0],["confusion4"]))
    
    #get the confusion pixels for confusion5 - snow and ice
    image = image.addBands(image.expression(confusion5a).select([0],["conf5a"]))
    image = image.addBands(image.expression(confusion5b).select([0],["conf5b"]))
    image = image.addBands(image.expression(confusion5c).select([0],["conf5c"]))
    image = image.addBands(image.select(["conf5.*"]).reduce(ee.Reducer.allNonZero()).select([0],["confusion5"]))
    
    #get the confusion pixels for confusion6 - remove water detection where it is outside the valid temperature range
    image = image.addBands(ee.call('Image.not',image.expression(confusion6)).select([0],["confusion6"])) 
    
    #get the total confusion areas
    image = image.addBands(image.select(["confusion.*"]).reduce(ee.Reducer.anyNonZero()).multiply(3).select([0],["confusionAll"])) #confusion is class 3
    
    #add the water3 class which is where there is SWIR data <0 (which can only be water)
    image = image.addBands(image.expression(water3).multiply(4).select([0],["water3"]))
    
    #get the classes
    image = image.addBands(ee.ImageCollection([ee.Image(ee.call('Image.not',image.select(["cloudAndWater"],["c"])).toInt()),ee.Image(image.select(["water"],["c"])),ee.Image(image.select(["confusionAll"],["c"])),ee.Image(image.select(["water3"],["c"]))]).max().select([0],["classesMax"])) #water where swir<0 = 4, confusion = 3, water = 2, not-water/cloud = 1, cloud = 0
    image = image.addBands(image.remap([4,3,2,1,0],[2,1,2,1,0],0,"classesMax").select([0],["classesRemapped"])) # water = 2, not-water or cloud = 1, cloud = 0
    
    #get the clouds and mask them
    image = image.addBands(image.expression("b('cloudAndWater')==1&&b('classesRemapped')!=2&&b('TIR')<" + str(cloudMaxTemperature)).select([0],["cloudMask"]))
    image = image.addBands(image.select(["classesRemapped"]).multiply(ee.call('Image.not',image.select(["cloudMask"]))).select([0],["classesMasked"]))
    
    #get the valid observations and add them back in where there is only cloud left
    image = image.addBands(ee.call('Image.and',image.expression(validObservation),image.expression("b('classesMasked')==0")).select([0],["validObservation"]))
    image = image.addBands(image.select(["classesMasked"]).add(image.select(["validObservation"])).select([0],["classes"]))
    
    #mask out any missing data, e.g. SLC in Landsat 7
    image = image.addBands(image.select(["classes"]).multiply(ee.call('Image.not',image.expression(missingDataExpression))).select([0],["class"]))
    image = image.addBands(image.select(["class"]).mask(image.select(["class"])).subtract(1).select([0],["detection"])) #water = 1, not-water = 0, no-data = masked
    return image.select(["detection"])

def authenticate():
    # this now uses a credentials file on the server
    credentials = GetCredentials()
    ee.Initialize(credentials)
    
def GetCredentials():
  # Read persistent credentials from /srv/www/dopa-services/cgi-bin/google earth engine/credentials
  try:
    tokens = json.load(open("../../../../../srv/www/dopa-services/cgi-bin/google earth engine/credentials"))
    refresh_token = tokens['refresh_token']
    return oauth2client.client.OAuth2Credentials(None, OAuthInfo.CLIENT_ID, OAuthInfo.CLIENT_SECRET, refresh_token, None, 'https://accounts.google.com/o/oauth2/token', None)
  except IOError:
    script = os.path.join(os.path.dirname(os.path.realpath(__file__)),'authenticate.py')
    raise EEException('Please authorize access to your Earth Engine account by running\n\n%s %s\n\nand then retry.' %(sys.executable, script))