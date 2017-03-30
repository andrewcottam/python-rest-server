CREATE OR REPLACE FUNCTION especies._get_glc2000_categories()
  RETURNS TABLE(land_cover text, color text) AS
$BODY$

SELECT glc2000_categories.land_cover,glc2000_categories.color FROM  especies.glc2000_categories ORDER BY 1
--SELECT DISTINCT   glc2000_categories.land_cover,   glc2000_categories.color FROM   especies.gee_training_data,   especies.glc2000_categories WHERE   gee_training_data.land_cover = glc2000_categories.land_cover ORDER BY 1
$BODY$
  LANGUAGE sql VOLATILE
  COST 100
  ROWS 1000;
ALTER FUNCTION especies._get_glc2000_categories()
  OWNER TO h05googleearthengine;
COMMENT ON FUNCTION especies._get_glc2000_categories() IS 'Gets the GLC 2000 legend categories and their colours';

-- Function: especies._get_gee_validation_sites(double precision, double precision, double precision, double precision)

-- DROP FUNCTION especies._get_gee_validation_sites(double precision, double precision, double precision, double precision);

CREATE OR REPLACE FUNCTION especies._get_gee_validation_sites(
    IN llx double precision,
    IN lly double precision,
    IN urx double precision,
    IN ury double precision)
  RETURNS TABLE(oid integer, land_cover text, lat double precision, lng double precision, sensor text, sceneid text, image_date timestamp with time zone, band1 double precision, band2 double precision, band3 double precision, band4 double precision, band5 double precision, band6 double precision, band7 double precision, band8 double precision, band9 double precision, band10 double precision, band11 double precision, bqa integer, hue double precision, saturation double precision, value double precision, ndvi double precision, ndwi double precision, username text, entry_date timestamp with time zone) AS
$BODY$  
SELECT gee_training_data.oid::integer,land_cover, lat, lng, sensor, sceneid, image_date, band1, band2, 
       band3, band4, band5, band6, band7, band8, band9, band10, band11, 
       bqa, hue, saturation, value, ndvi,ndwi,username, entry_date FROM especies.gee_training_data WHERE lng BETWEEN $1 AND $3 AND lat BETWEEN $2 AND $4;
$BODY$
  LANGUAGE sql VOLATILE
  COST 100
  ROWS 1000;
ALTER FUNCTION especies._get_gee_validation_sites(double precision, double precision, double precision, double precision)
  OWNER TO h05googleearthengine;
COMMENT ON FUNCTION especies._get_gee_validation_sites(double precision, double precision, double precision, double precision) IS 'Returns the location of Google Earth Engine Validation sites and their respective lat/long coordinates within a bounding box.';

-- Function: especies._get_gee_validation_site(integer)

-- DROP FUNCTION especies._get_gee_validation_site(integer);

CREATE OR REPLACE FUNCTION especies._get_gee_validation_site(IN oid integer)
  RETURNS TABLE(oid integer, land_cover text, lat double precision, lng double precision, sensor text, sceneid text, image_date timestamp with time zone, band1 double precision, band2 double precision, band3 double precision, band4 double precision, band5 double precision, band6 double precision, band7 double precision, band8 double precision, band9 double precision, band10 double precision, band11 double precision, bqa integer, hue double precision, saturation double precision, value double precision, ndvi double precision, ndwi double precision, username text, entry_date timestamp with time zone) AS
$BODY$  
SELECT oid::integer, land_cover, lat, lng, sensor, sceneid, image_date, band1, band2, 
       band3, band4, band5, band6, band7, band8, band9, band10, band11, 
       bqa, hue, saturation, value, ndvi,ndwi,username, entry_date FROM especies.gee_training_data WHERE gee_training_data.oid=$1;
$BODY$
  LANGUAGE sql STABLE
  COST 100
  ROWS 1000;
ALTER FUNCTION especies._get_gee_validation_site(integer)
  OWNER TO h05googleearthengine;
COMMENT ON FUNCTION especies._get_gee_validation_site(integer) IS 'Returns the Google Earth Engine Validation Site with the corresponding oid';

-- Function: especies._delete_gee_validation_record(integer)

-- DROP FUNCTION especies._delete_gee_validation_record(integer);

CREATE OR REPLACE FUNCTION especies._delete_gee_validation_record(oid integer)
  RETURNS text AS
$BODY$
BEGIN
delete from especies.gee_training_data where gee_training_data.oid=$1;
RETURN FOUND;
END
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION especies._delete_gee_validation_record(integer)
  OWNER TO h05googleearthengine;
COMMENT ON FUNCTION especies._delete_gee_validation_record(integer) IS 'Deletes a record from the Google Earth Engine validation table';

-- Function: especies._get_path_row(double precision, double precision)

-- DROP FUNCTION especies._get_path_row(double precision, double precision);

CREATE OR REPLACE FUNCTION especies._get_path_row(
    IN lat double precision,
    IN lng double precision)
  RETURNS TABLE(path smallint, "row" smallint) AS
$BODY$
SELECT path,row from especies.landsat_wrs2 where st_Intersects(ST_SetSRID(ST_Point($2,$1),4326), landsat_wrs2.geom)='t';
  $BODY$
  LANGUAGE sql STABLE
  COST 100
  ROWS 1000;
ALTER FUNCTION especies._get_path_row(double precision, double precision)
  OWNER TO h05googleearthengine;
COMMENT ON FUNCTION especies._get_path_row(double precision, double precision) IS 'Returns the Landsat WRS2 Path/Row identiers for the passed lat/long coordinate';

-- Function: especies._get_gee_detection_algorithms(text)

-- DROP FUNCTION especies._get_gee_detection_algorithms(text);

CREATE OR REPLACE FUNCTION especies._get_gee_detection_algorithms(IN username text)
  RETURNS TABLE(algorithm_oid integer, algorithm text) AS
'select oid::integer,algorithm from especies.gee_detection_algorithms where username=$1 order by 2;'
  LANGUAGE sql VOLATILE
  COST 100
  ROWS 1000;
ALTER FUNCTION especies._get_gee_detection_algorithms(text)
  OWNER TO h05googleearthengine;
COMMENT ON FUNCTION especies._get_gee_detection_algorithms(text) IS 'Returns a set of detection algorithms';

-- Function: especies._insert_gee_detection_algorithm(text, text)

-- DROP FUNCTION especies._insert_gee_detection_algorithm(text, text);

CREATE OR REPLACE FUNCTION especies._insert_gee_detection_algorithm(
    algorithm text,
    username text)
  RETURNS integer AS
$BODY$
DECLARE
resultOID integer;
BEGIN
INSERT INTO especies.gee_detection_algorithms(algorithm, username) VALUES ($1,$2);
GET DIAGNOSTICS resultOID = RESULT_OID;
RETURN resultOID;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION especies._insert_gee_detection_algorithm(text, text)
  OWNER TO h05googleearthengine;
COMMENT ON FUNCTION especies._insert_gee_detection_algorithm(text, text) IS 'inserts a detection algorithms';

-- Function: especies._delete_gee_detection_algorithm(integer)

-- DROP FUNCTION especies._delete_gee_detection_algorithm(integer);

CREATE OR REPLACE FUNCTION especies._delete_gee_detection_algorithm(algorithm_oid integer)
  RETURNS boolean AS
$BODY$
BEGIN
DELETE FROM especies.gee_detection_algorithms WHERE oid = $1;
RETURN FOUND;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION especies._delete_gee_detection_algorithm(integer)
  OWNER TO h05googleearthengine;
COMMENT ON FUNCTION especies._delete_gee_detection_algorithm(integer) IS 'Deletes a detection algorithm from the gee_detection_algorithms table';

-- Function: especies._update_gee_detection_algorithm(integer, text)

-- DROP FUNCTION especies._update_gee_detection_algorithm(integer, text);

CREATE OR REPLACE FUNCTION especies._update_gee_detection_algorithm(
    algorithm_oid integer,
    algorithm text)
  RETURNS boolean AS
$BODY$
BEGIN
UPDATE especies.gee_detection_algorithms SET algorithm = $2 WHERE oid = $1;
RETURN FOUND;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION especies._update_gee_detection_algorithm(integer, text)
  OWNER TO h05googleearthengine;
COMMENT ON FUNCTION especies._update_gee_detection_algorithm(integer, text) IS 'Updates a detection algorithm in the gee_detection_algorithms table';

-- Function: especies.get_user_api_key(text, text)

-- DROP FUNCTION especies.get_user_api_key(text, text);

CREATE OR REPLACE FUNCTION especies.get_user_api_key(
    username text,
    password text)
  RETURNS text AS
$BODY$select '1'::text$BODY$
  LANGUAGE sql VOLATILE
  COST 100;
ALTER FUNCTION especies.get_user_api_key(text, text)
  OWNER TO h05googleearthengine;
COMMENT ON FUNCTION especies.get_user_api_key(text, text) IS 'Returns a user_api_key for the passed credentials or none if the user cannot be authenticated. The api_key is used in secure services.';

