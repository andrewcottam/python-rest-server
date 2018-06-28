import math, pandas, fiona
import geopandas as gpd
from shapely.geometry import Point, Polygon
from fiona.crs import from_epsg
from math import floor, ceil

def CreateHexGrid(area, xleft, ybottom, xright, ytop, savename):
    #error checks
    if area < 0:
        return "Area is invalid"
        
    if len(savename) <= 0:
        return "No output filename given"
    
    if (xleft >= xright):
        return "Invalid extent width: " + unicode(xleft) + " - " + unicode(xright)
    
    if (ybottom >= ytop):
        return "Invalid extent height: " + unicode(ybottom) + " - " + unicode(ytop)
    
    #calculate the spacing between the hexagons to give you the required area
    sideLength = math.sqrt((2*area)/(3*math.sqrt(3)))
    xspacing = sideLength + (sideLength * 0.5) # the cos(60) = 0.5
    yspacing = xspacing / 0.866025

    #create a new geodataframe to store the hexagons
    newdata = gpd.GeoDataFrame()
    
    #set the coordinate reference systems as 3410 (NSIDC Ease-Grid Global) - An equal area projection
    # newdata.crs = from_epsg(4326)
    newdata.crs = from_epsg(3410)
    
    #create the geometry field and an id field
    newdata['geometry'] = None
    newdata['id'] = None
    
    #get the number of rows/columns
    rows = int(ceil((ytop - ybottom) / yspacing))
    columns = int(ceil((xright - xleft) / xspacing))
    
    #initialise the feature counter
    feature_count = 0
    
    #THE FOLLOWING CODE COMES FROM MICHAEL MINN'S MMQGIS PLUGIN - http://michaelminn.com/linux/mmqgis/
    
    # To preserve symmetry, hspacing is fixed relative to vspacing
    xvertexlo = 0.288675134594813 * yspacing
    xvertexhi = 0.577350269189626 * yspacing
    xspacing = xvertexlo + xvertexhi

    for column in range(0, int(floor(float(xright - xleft) / xspacing))):
        # (column + 1) and (row + 1) calculation is used to maintain 
        # topology between adjacent shapes and avoid overlaps/holes 
        # due to rounding errors

        x1 = xleft + (column * xspacing)    # far left
        x2 = x1 + (xvertexhi - xvertexlo)    # left
        x3 = xleft + ((column + 1) * xspacing)    # right
        x4 = x3 + (xvertexhi - xvertexlo)    # far right

        for row in range(0, int(floor(float(ytop - ybottom) / yspacing))):

            if (column % 2) == 0:
                y1 = ybottom + (((row * 2) + 0) * (yspacing / 2))    # hi
                y2 = ybottom + (((row * 2) + 1) * (yspacing / 2))    # mid
                y3 = ybottom + (((row * 2) + 2) * (yspacing / 2))    # lo
            else:
                y1 = ybottom + (((row * 2) + 1) * (yspacing / 2))    # hi
                y2 = ybottom + (((row * 2) + 2) * (yspacing / 2))    # mid
                y3 = ybottom + (((row * 2) + 3) * (yspacing / 2))    #lo

            #create the coordinates of the hexagon
            coordinates = [(x1, y2), (x2, y1), (x3, y1), (x4, y2), (x3, y3), (x2, y3), (x1, y2)]
            
            #cretae a polygon with the coordinates
            poly = Polygon(coordinates)

            #set the geometry
            newdata.loc[feature_count, 'geometry'] = poly

            #set the feature id
            newdata.loc[feature_count, 'id'] = feature_count
            
            #increment the counter
            feature_count = feature_count + 1
    
    # Write the data into that Shapefile
    newdata.to_file(savename)

#get the hexagon side length for the required area
area = 10000000
xleft = 6676
ybottom = 860924
xright = 43711
ytop = 878065
savename = r"/home/ubuntu/workspace/test_hexagon.shp"

CreateHexGrid(area, xleft, ybottom, xright, ytop, savename)
