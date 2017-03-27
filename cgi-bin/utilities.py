from pyproj import Proj
from pyproj import transform

def getPointLL(point_x, point_y, crs):
        p1, p2 = getProjections(crs)
        ll_long, ll_lat = transform(p1, p2, point_x, point_y)  # transform the data to lat/long so that we can use it in Google Earth Engine
        return ll_long, ll_lat

def getProjections(crs):
        if crs.upper() == "EPSG:102100":
            p1 = Proj(init='epsg:3857')
        else:
            p1 = Proj(init=crs)
        p2 = Proj(init='epsg:4326')
        return p1, p2    

