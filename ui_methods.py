def getqueryparams(obj, params, queryparams):
	for param in params:
		value = "1"
		if (param['name'] in ['country']):
			 value = "Honduras"
		if (param['name'] in ['country_id','countryid']):
			 value = "458"
		elif (param['name'] in ['wdpa_id','wdpaid']):
			 value = "785" 
		elif (param['name'] in ['iucn_species_id','species_id','speciesid']):
			 value = "17975"
		elif (param['name'] in ['ecoregionid']):
			 value = "10122"
		elif (param['name'] in ['startdate']):
			 value = "20120101"
		elif (param['name'] in ['enddate']):
			 value = "20121221"
		elif (param['name'] in ['latitude']):
			 value = "4.7374874801628"
		elif (param['name'] in ['longitude']):
			 value = "117.1214580575966"
		elif (param['name'] in ['taxongroup']):
			 value = "aves"
		elif (param['name'] in ['language2']):
			 value = "english"
		elif (param['name'] in ['language1']):
			 value = "french"
		elif (param['name'] in ['quadkey']):
			 value = "132320330230021"
		elif (param['name'] in ['grouping_id']):
			 value = "ACP - Central Africa"
		elif (param['name'] in ['searchterm']):
			 value = "Sa"
		if (param['type']=='array'):
			if (param['default']!=''):
				if ',' in param['default']:
					 value = param['default'].split(',')[0] + ',' + param['default'].split(',')[1]
				else:
					 value = param['default']
			else:
				if (param['name'] in ['wdpa_ids']):
					 value = "901237,785,220292"
				else: 
					 value = "1,2"
		if (param['type']=='date'):
			 value = "03/31/2012"
		if (param['type']=='datetime'):
			 value = "03/31/2012 10:15:25"
		queryparams.append(param['name'] + "=" + value)