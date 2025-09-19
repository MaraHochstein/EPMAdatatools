#######################
# imports
#######################
from utils.imports import (st, sst, requests, urllib, datetime, pd, io, re, os, io, re, os, Image, tiff, base64, imagecodecs, html, copy, alt, np, go, openpyxl)
import utils.func as fn

import json
import time

#########################
# helper functions
#########################

# get fill colors from xlsx file
def getXlsxFillColors(sheet):
    fillColors = {}
    for row in sheet.iter_rows():
        for cell in row:
            # check if cell is colored
            if cell.fill and cell.fill.fgColor and hasattr(cell.fill.fgColor, 'tint') and cell.fill.fgColor.tint != 0:
                fillColors[(cell.row - 1, cell.column - 1)] = True # mark cell for styling
    return fillColors

# color cells in pd.df
def colorCells(data, fillColors, origData, color):  
    # map original row/col positions to new df structure (after changing indices)
    origPositions = {}
    for (origRow, origCol), _ in fillColors.items():
        if origRow < len(origData) and origCol < len(origData.columns):
            newRowName = origData.iloc[origRow, 0] # first col gets index
            newColName = origData.iloc[0, origCol] # first row gets header
            origPositions[(newRowName, newColName)] = True
    # apply color
    def applyColor(row):
        return [
            'background-color: ' + color if (row.name, col) in origPositions else ''
            for col in row.index
        ]
    return data.style.apply(lambda x: applyColor(x), axis=1)  


#########################
# Kadi4Mat functions
#########################

# get data from kadi api
@st.cache_data(show_spinner=False)
def kadiGetData(url):
    urlPrefix = 'https://kadi4mat.iam.kit.edu/api/'
    if sst.kadiPAT == '':
        authPAT = st.secrets['kadiPAT']
    else:
        authPAT = sst.kadiPAT
    response = requests.get(urlPrefix+url, headers={'Authorization': 'Bearer ' + authPAT})
    return response


# get records from user
def kadiGetUserRecords():
    with st.spinner('Loading records from profile, please wait...', show_time=True):
        # clear from previous run
        sst.userRecords = {}
        
        # get records that are only visible for the user -> also shared (= private)
        response = kadiGetData('records?visibility=private&per_page=100') # per_page max = 100
        maxPages = response.json()['_pagination']['total_pages'] # get total pages of files for this record (one page has 100 files max)
        page=1
        while page<(maxPages+1): # cycle trough pages
            response = kadiGetData('records?visibility=private&per_page=100&page=' + str(page))
            allItems = response.json()
            page+=1
            # check item ids & names
            for item in allItems['items']:
                sst.userRecords[item['id']] = item['identifier']
        
        # get records of the user himself that are public
        response = kadiGetData('records?visibility=public&user=' + str(sst.kadiUserID) + '&per_page=100') # per_page max = 100
        maxPages = response.json()['_pagination']['total_pages'] # get total pages of files for this record (one page has 100 files max)
        page=1
        while page<(maxPages+1): # cycle trough pages
            response = kadiGetData('records?visibility=public&user=' + str(sst.kadiUserID) + '&per_page=100&page=' + str(page))
            allItems = response.json()
            page+=1
            # check item ids & names
            for item in allItems['items']:
                sst.userRecords[item['id']] = item['identifier']


# get records from group
def kadiGetGroupRecords():
    with st.spinner('Loading records from IfG GUF, please wait...', show_time=True):
        # clear from previous run
        sst.userRecords = {}
        response = kadiGetData('groups/158/records?per_page=100') # per_page max = 100
        maxPages = response.json()['_pagination']['total_pages'] # get total pages of files for this record (one page has 100 files max)
        page=1
        while page<(maxPages+1): # cycle trough pages
            response = kadiGetData('groups/158/records?per_page=100&page=' + str(page))
            allItems = response.json()
            page+=1
            # check item ids & names
            for item in allItems['items']:
                sst.userRecords[item['id']] = item['identifier']
                

# get kadi Metadata to session state
def kadiGetMetadata():
    response = kadiGetData('records/' + str(sst.recordID) + '/extras/export/json')
    # write kadi Metadata to session state
    firstCol = []
    dataCol = []               
    for i in range(1,len(response.json())):
                if response.json()[i]['key'] != 'password':
                    firstCol.append(response.json()[i]['key'])
                    if response.json()[i]['value'] == None:
                        valueWithUnit = '\-'
                    else:
                        valueWithUnit = str(response.json()[i]['value'])
                    if 'unit' in response.json()[i]:
                        valueWithUnit = valueWithUnit + ' ' + str(response.json()[i]['unit'])
                    dataCol.append(valueWithUnit)
    
    
    metadata = pd.concat([pd.DataFrame({'Value': [kadiGetData('records/' + sst.recordID).json()['description']]}, index=['description']), pd.DataFrame(data=dataCol, index=firstCol, columns=['Value'])])
    metadata.index = metadata.index.str.capitalize()
    
    sst.kadiMetaData = metadata


# get specific metadata field
def getMetadataValue(data, metaname):  
    for item in data:
        if item.get('key') == metaname:
            return item.get('value')
    return ''


# load files from kadi & combine them         
def kadiLoadFiles(parentContainer = False):
    # load only if record id is specified (per button [demo] dropdown [ag/kadi] / input field [kadi]) and if there is no fully loaded data in sst
    if not (sst.recordID == '' or sst.kadiLoaded == 1):
        try:
            with st.status('Loading data, please wait ...', expanded = True) as kadiStatus:
                ################
                # Init & Clean
                ################
                # clear from previous upload (if upload was only partly successful)
                sstVars = ['kadiLoaded', 'kadiMetaData', 'condElements', 'condInfos', 'condMapInfos', 'condSamples', 'condMapSamples', 'condStd', 'methodGeneralData', 'methodSampleData', 'methodStdData', 'shortMeasCond', 'standardsXlsx', 'standardsXlsxExport', 'csvMerged', 'kadiFilter', 'imageData', 'imageFiles', 'mapData', 'mapFilter', 'mapGeneralData', 'mapWdsData', 'mapEdsData', 'qualiConditions', 'methodQualiGeneralData', 'qualiSpectra', 'methodQualiSpecData', 'qualitativeSpectraXlsx']
                for var in sstVars:
                    fn.resetVar(var)
                
                # temp variables(raw filenames & data)
                csvSummaryFile = {}
                csvSummaryData = pd.DataFrame()
                csvSummaryName = 'summary[timestamp].csv'
                
                normalFile = {}
                normalContent = ''
                normalName = 'normal.txt'
                
                quickFile = {}
                quickData = ''
                quickName = 'quick standard.txt'
                
                standardFile = {}
                standardData = ''
                standardName = 'summary standard.txt'
                
                standardsXlsxFile = {}
                standardsXlsxData = ''
                standardsXlsxName = 'standards.xlsx'
                
                qualiSpectraXlsxFile = {}
                qualiSpectraXlsxData = ''
                qualiSpectraXlsxName = 'qualitative spectra.xlsx'
                
                qualiSpectraQuickFile = {}
                qualiSpectraQuickData = ''
                qualiSpectraQuickName = 'quick standard quali.txt'
                
                mapJsons = {}
                mapJsonsData = {}
                mapJsonName = 'map [sample name].json'
                
                kadiError = False
                kadiFilter = {}
                
                imageFiles = {}
                
                mapFiles = {}
                mapFilter = {}
                
                # get kadi metadata for record
                st.write(':material/cloud_download: Getting metadata from Kadi4Mat ...')
                kadiGetMetadata()
                
                
                ############################################################################
                # Loading order:
                #   1. get file ids from record
                #   2. check if all raw files are found
                #   3. load content of raw files
                #   4. merge files
                #   5. load saved filter settings from kadi
                # ---- maps & imgs after merging to decrease loading time if error occurs
                #   6. load map files
                #   7. load image files 
                ############################################################################
                

                ##########################################
                # 1. get file ids from record
                ##########################################
                
                # get all filenames from api
                st.write(':material/quick_reference_all: Checking files for raw EPMA data ...')
                response = kadiGetData('records/' + sst.recordID + '/files?per_page=100') # per_page max = 100
                maxPages = response.json()['_pagination']['total_pages'] # get total pages of files for this record (one page has 100 files max)
                
                page=1
                while page<(maxPages+1): # cycle trough pages
                    response = kadiGetData('records/' + sst.recordID + '/files?per_page=100&page=' + str(page))
                    allItems = response.json()
                    page+=1
                    
                    # check files for raw-data filetypes
                    for item in allItems['items']:
                        # normal file
                        if normalName in item['name'] and item['mimetype'] == 'text/plain':
                            normalFile[item['id']] = item['name']
                        # quick file
                        elif quickName in item['name'] and item['mimetype'] == 'text/plain':
                            quickFile[item['id']] = item['name']
                        # standard file
                        elif standardName in item['name'] and item['mimetype'] == 'text/plain':
                            standardFile[item['id']] = item['name']
                        # csv summary
                        elif item['mimetype'] == 'text/csv' and item['name'].startswith('summary'):
                            csvSummaryFile[item['id']] = item['name']
                        # standards.xlsx
                        elif item['mimetype'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' and item['name'] == standardsXlsxName:
                            standardsXlsxFile[item['id']] = item['name']
                        # qualitative spectra.xlsx
                        elif item['mimetype'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' and item['name'] == qualiSpectraXlsxName:
                            qualiSpectraXlsxFile[item['id']] = item['name']
                        # quick standard quali.txt
                        elif qualiSpectraQuickName in item['name'] and item['mimetype'] == 'text/plain':
                            qualiSpectraQuickFile[item['id']] = item['name']
                        # map parameter jsons
                        elif item['name'].startswith('map ') and item['mimetype'] == 'application/json':
                            mapJsons[item['id']] = item['name']                        
                        # images
                        elif item['mimetype'] == 'image/tiff' or item['mimetype'] == 'image/jpeg':
                            imageFiles[item['id']] = item['name']
                        # filter
                        elif 'filter' in item['name'] and item['mimetype'] == 'text/plain':
                            kadiFilter[item['id']] = item['name']
                        # maps
                        elif item['name'].startswith('map ') and item['mimetype'] == 'text/csv':
                            mapFiles[item['id']] = item['name']
                        # map settings
                        elif 'mapSettings' in item['name'] and item['mimetype'] == 'text/plain':
                            mapFilter[item['id']] = item['name']
                        
                
                ############################################################
                # 2. check if all raw files are found
                # - 2a. optional files for all measurement types
                # - 2b. QUANT (or MAPS + QUANT)
                # - 2c. MAPS ONLY
                # - 2end. Error messages if missing & double files -> stop
                ############################################################
                
                missingFiles = []
                doubleFiles = []
                doubleFileNames = []
                
                # 2a. optional files for all measurement types
                # - standards.xlsx
                # - qualitative spectra.xlsx
                # - quick standard quali.txt
                #################################################
                if len(standardsXlsxFile) > 1:
                    doubleFiles.append(standardsXlsxName + '-file')
                    doubleFileNames.append(' / '.join(standardsXlsxFile.values()))
                
                if len(qualiSpectraXlsxFile) > 1:
                    doubleFiles.append(qualiSpectraXlsxName + '-file')
                    doubleFileNames.append(' / '.join(qualiSpectraXlsxFile.values()))
                    
                if len(qualiSpectraQuickFile) > 1:
                    doubleFiles.append(qualiSpectraQuickName + '-file')
                    doubleFileNames.append(' / '.join(qualiSpectraQuickFile.values()))
                
                # 2b. QUANT (or MAPS + QUANT)
                # - summary[timestamp].csv
                # - normal.txt
                # - quick standard.txt
                # - summary standard.txt
                ################################
                
                if (len(csvSummaryFile) >= 1 and len(normalFile) >= 1 and len(quickFile) >= 1 and len(standardFile) >= 1):
                
                    if len(csvSummaryFile) < 1:
                        missingFiles.append(csvSummaryName + '-file')
                    elif len(csvSummaryFile) > 1:
                        doubleFiles.append(csvSummaryName + '-file')
                        doubleFileNames.append(' / '.join(csvSummaryFile.values()))
                    if len(normalFile) < 1:
                        missingFiles.append(normalName + '-file')
                    elif len(normalFile) > 1:
                        doubleFiles.append(normalName + '-file')
                        doubleFileNames.append(' / '.join(normalFile.values()))
                    if len(quickFile) < 1:
                        missingFiles.append(quickName + '-file')
                    elif len(quickFile) > 1:
                        doubleFiles.append(quickName + '-file')
                        doubleFileNames.append(' / '.join(quickFile.values()))
                    if len(standardFile) < 1:
                        missingFiles.append(standardName + '-file')
                    elif len(standardFile) > 1:
                        doubleFiles.append(standardName + '-file')
                        doubleFileNames.append(' / '.join(standardFile.values()))
                
                # 2c. MAPS ONLY
                # - json
                ##############################
                
                if len(mapFiles) > 0 and sst.importMaps:
                    if len(mapJsons) < 1:
                        missingFiles.append(mapJsonName + '-file(s)')
                
                
                # 2end. ERROR MESSAGES
                ########################
                
                # missing files
                if len(missingFiles) > 0:
                    line1 = (('Please upload the following files to [**this record**&thinsp;:link:](https://kadi4mat.iam.kit.edu/records/') if len(missingFiles) > 1 else ('Please upload the following file to [**this record**&thinsp;:link:](https://kadi4mat.iam.kit.edu/records/')) + str(sst.recordID) + '?tab=files) and try again'
                    line2 = '\n' + '\n'.join([f'- {file}' for file in missingFiles])
                    st.error(f'''
                        {line1}
                        {line2}
                        ''', icon=':material/sync_problem:')
                
                # double files
                if len(doubleFiles) > 0:
                    line1 = ('Found multiple possible raw files of the following filetypes') if len(doubleFiles) > 1 else ('Found multiple possible raw files of the following filetype')
                    line2 = '\n' + '\n'.join([f'- {file}' for file in doubleFiles])
                    line3 = (('\n Please remove or rename one of these files') if len(doubleFiles) > 1 else ('\n Please remove or rename one of the corresponding files')) + 'in [**this record**&thinsp;:link:](https://kadi4mat.iam.kit.edu/records/' + str(sst.recordID) + '?tab=files) and try again'
                    line4 = '\n' + '\n'.join([f'- {file}' for file in doubleFileNames])
                    st.error(f'''   
                        {line1}
                        {line2}
                        {line3}                            
                        {line4}
                        ''', icon=':material/sync_problem:')
                
                # stop if missing or double files
                if len(missingFiles) > 0 or len(doubleFiles) > 0:
                    kadiStatus.update(label='Something went wrong, please read the corresponding error message for details.', state='error', expanded=True)
                    kadiError = True
                    st.stop()
                
                
                ###########################################################
                # 3. load content of raw files
                # - 3a. optional files for all measurement types
                # - 3b. QUANT (or MAPS + QUANT)
                # - 3c. MAPS ONLY
                # - 3d. QUALITATIVE SPECTRA
                # - 3end. check if all contain data -> else error & stop
                ###########################################################
                
                st.write(':material/cloud_download: Loading raw EPMA data ...')
                invalidFiles = []
                
                # 3a. optional for all measurement types
                # - 3a1. standards.xlsx (standardsXlsxFile)
                #################################################
                # optional
                if len(standardsXlsxFile) == 1:
                    content = kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + list(standardsXlsxFile.keys())[0] + '/download')
                    # use bytesIO for decoding xlsx format
                    xlsxData = io.BytesIO(content)
                    xlsxWb = openpyxl.load_workbook(xlsxData, data_only=True)
                    
                    # for every sheet (if multiple standard measurements)
                    for sheet in xlsxWb.sheetnames:
                        # get sheet
                        xlsxSheet = xlsxWb[sheet]
                        
                        # check if there are multiple tables in the sheet (data, two empty rows, more data)
                        moreContent = False
                        emptyRows = 0
                        
                        for row in xlsxSheet.iter_rows(min_row=1, max_row=xlsxSheet.max_row, max_col=xlsxSheet.max_column):
                            # check if row is empty
                            if all(cell.value is None for cell in row):
                                emptyRows += 1
                            else:
                                # row is not empty -> check if empty rows are > 0
                                if emptyRows > 0 and moreContent:
                                    st.warning('Your ' + standardsXlsxName + '-file has an invalid structure and could not be imported.', icon=':material/sync_problem:')
                                    moreContent = True # mark more content
                                    emptyRows = 0 # reset empty rows after content
                                    break
                        if emptyRows > 0: # empty rows before last content
                            st.warning('Your ' + standardsXlsxName + '-file has an invalid structure and could not be imported.', icon=':material/sync_problem:')
                            moreContent = True
                        
                        # continue if content is ok
                        if not moreContent:
                            # get fill colors & data
                            ## extract fill colors
                            fillColors = getXlsxFillColors(xlsxSheet)
                            ## convert sheet to pd.df
                            xlsxDf = pd.DataFrame(xlsxSheet.values)
                            xlsxDfOrig = xlsxDf.copy()
                            ## save shape of df
                            xlsxShape = xlsxDf.shape
                            ## set first row as header row (transpose, set index, transpose back is shortest)
                            xlsxDf = xlsxDf.T.set_index(xlsxDf.columns[0]).T
                            ## set first col as index col
                            xlsxDf = xlsxDf.set_index(xlsxDf.columns[0])
                            
                            # save in sst
                            ## color cells in the pd.df if they have color in xlsx-file                            
                            sst.standardsXlsx[sheet] = colorCells(xlsxDf, fillColors, xlsxDfOrig, st.get_option('theme.primaryColor')) # use shape of original xlsx
                            ## use different color for excel export (streamlit theme color would change to black in export)
                            sst.standardsXlsxExport[sheet] = colorCells(xlsxDf, fillColors, xlsxDfOrig, 'lightblue')
                
                
                # 3b. QUANT (or MAPS + QUANT)
                # - 3b1. summary[timestamp].csv (csvSummaryFile)
                # - 3b2. normal.txt (normalFile)
                # - 3b3. quick standard.txt (quickFile)
                # - 3b4. summary standard.txt (standardFile)
                #####################################################
                
                if (len(csvSummaryFile) == 1 and len(normalFile) == 1 and len(quickFile) == 1 and len(standardFile) == 1):    
                    
                    # 3b1. load summary[timestamp].csv -> csvSummaryData
                    ######################################################
                    content = kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + list(csvSummaryFile.keys())[0] + '/download').decode('utf_8')
                    lines = content.splitlines()
                    # search content for header row (to get skiprows)
                    skipRows = 0
                    for lineNumber, line in enumerate(lines, start=1):
                        if 'Total' in line:
                            skipRows = lineNumber - 1
                            break
                    # search content for first empty row after header (to get skipfooter)
                    skipFooter = 0
                    for lineNumber in range(skipRows + 1, len(lines) + 1):
                        line = lines[lineNumber - 1]
                        if ',,,,,' in line:
                            skipFooter = len(lines) - lineNumber + 1
                            break
                    # save content for merging
                    if len(content) > 2:
                        csvSummaryData = pd.read_csv(io.StringIO(content), skiprows=skipRows, skipfooter=skipFooter, engine='python')
                        
                        # change duplicate names in Comment for merging
                        duplicateComments = {} # keeps track of duplicates
                        for i, comment in enumerate(csvSummaryData['Comment']):
                            if comment in duplicateComments:
                                # increase count for each occurance of comment (sample name)
                                duplicateComments[comment] += 1
                                # change name of comment if comment was 
                                csvSummaryData.at[i, 'Comment'] = comment + '_dupl' + str(duplicateComments[comment])
                            else:
                                # first occurance of each comment (sample name) -> make entry
                                duplicateComments[comment] = 0
                        
                        
                    else:
                        invalidFiles.append(csvSummaryName + '-file')
                        
                    # 3b2. load normal.txt
                    ########################
                    content = kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + list(normalFile.keys())[0] + '/download').decode('utf_8')
                    
                    # text-file contains something -> else append to invalid files
                    if len(content) > 2: 
                        normalContent = content
                        # find values in text
                        comment = [x.rstrip() for x in re.findall(r'Comment\s*:\s*(.*)(?:\n|\r\n)', normalContent)] # column for merging
                        datetimes = re.findall(r'Dated\son\s(\d{4}\/\d{2}\/\d{2}\s\d{2}:\d{2}:\d{2})', normalContent) # only in normal-file
                        diameters = re.findall(r'Probe\sDia.\s*:\s*(\d+\.\d+)', normalContent) # only in normal-file

                        # combine found values to df
                        normalData = pd.DataFrame(data=({'Comment': comment, 'Datetime': pd.to_datetime(datetimes, format='%Y/%m/%d %H:%M:%S'), 'Spotsize': [int(float(x)) for x in  diameters]}))
                        
                        # check if there are duplicates
                        normalDuplicates = normalData['Comment'].duplicated().any()
                        if normalDuplicates:
                            # show warning if duplicates
                            st.warning('Some Sample Names have been renamed to merge the raw data files. You can identify or filter these samples by the *_dupl*-suffix in the next step.', icon=':material/info:')
                        # change duplicate names in Comment for merging and give warning
                        duplicateComments = {}
                        for i, comment in enumerate(normalData['Comment']):
                            if comment in duplicateComments:
                                # increase count for each occurance of comment (sample name)
                                duplicateComments[comment] += 1
                                # change name of comment if comment was 
                                normalData.at[i, 'Comment'] = comment + '_dupl' + str(duplicateComments[comment])
                            else:
                                # first occurance of each comment (sample name) -> make entry
                                duplicateComments[comment] = 0
                        
                    else: # no content in normalFile
                        invalidFiles.append(normalName + '-file')  

                    # 3b3. load quick standard.txt
                    ################################
                    content = kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + list(quickFile.keys())[0] + '/download').decode('utf_8')            
                    if len(content) > 2: # text-file contains something
                        quickData = content
                    else:
                        invalidFiles.append(quickName + '-file')
                    
                    # 3b4. load standard summary standard.txt
                    ###########################################
                    content = kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + list(standardFile.keys())[0] + '/download').decode('utf_8')            
                    if len(content) > 2: # text-file contains something
                        standardData = content
                    else:
                        invalidFiles.append(standardName + '-file')  
                    
                # 3c. MAPS ONLY
                # - 3c1. json
                #################################
                
                if sst.importMaps:
                    if len(mapFiles) > 0 and len(mapJsons) > 0:
                        
                        # 3c1. load map jsons
                        ####################################
                        for i, mapJsonID in enumerate(mapJsons.keys()):
                            data = json.loads(kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + mapJsonID + '/download'))
                            if len(data) > 0: # json contains something
                                mapJsonsData[mapJsons[mapJsonID].rstrip('.json')] = data
                                st.write(mapJsonID)
                            else:
                                invalidFiles.append(mapJsonName + '-file(s)')
                
                # 3d. QUALITATIVE SPECTRA
                # - 3d1. xlsx
                # - 3d2. quick standard quali
                #################################
                
                if len(qualiSpectraXlsxFile) == 1:
                    
                    # 3d1. load qualitative spectra.xlsx
                    ###########################################
                    content = kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + list(qualiSpectraXlsxFile.keys())[0] + '/download')
                    # use bytesIO for decoding xlsx format
                    xlsxData = io.BytesIO(content)
                    xlsxWb = openpyxl.load_workbook(xlsxData, data_only=True)
                    
                    # for every sheet (if multiple measurements)
                    for sheet in xlsxWb.sheetnames:
                        # get sheet
                        xlsxSheet = xlsxWb[sheet]
                        # convert sheet to pd.df
                        xlsxDf = pd.DataFrame(xlsxSheet.values)
                        # set first row as header row (transpose, set index, transpose back is shortest)
                        xlsxDf = xlsxDf.T.set_index(xlsxDf.columns[0]).T
                        # save in sst                            
                        sst.qualitativeSpectraXlsx[sheet] = xlsxDf

                    # 3d2. load quick standard quali.txt
                    ###########################################
                    content = kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + list(qualiSpectraQuickFile.keys())[0] + '/download').decode('utf_8')            
                    if len(content) > 2: # text-file contains something
                        qualiSpectraQuickData = content
                    else:
                        invalidFiles.append(qualiSpectraQuickName + '-file')
                
                    
                # 3end. check if all raw files contain data for merging
                #########################################################
                if len(invalidFiles) > 0:
                    st.error(('The following files contain invalid data, please check them and try again: ') if len(invalidFiles) > 1 else ('The following file contains invalid data, please check the data and try again: ') + ', '.join(invalidFiles) + '.', icon=':material/sync_problem:')
                    kadiStatus.update(label='Invalid file data, please read the corresponding error message for details.', state='error', expanded=True)
                    kadiError = True
                    st.stop()


                ###################################
                # 4. merge files
                # - 4a. QUANT (or MAPS + QUANT)
                # - 4b. QUALITATIVE SPECTRA
                # - 4c. MAPS ONLY
                ###################################
                
                st.write(':material/merge: Merging files ...')
                
                
                # 4a. QUANT (or MAPS + QUANT)
                # -> find infos in txt-files & merge to sst-df's
                # - 4a1. Quantitative Conditions
                #        = sst.methodGeneralData, sst.methodSampleData, sst.methodStdData
                #        -> from quickData & standardData
                # - 4a2. Quantitative Data table
                #        =sst.csvMerged
                #        -> from csvSummaryData & normalData
                # - 4a3. Compact Measurement Conditions
                #        = sst.shortMeasCond
                #        -> from sst.methodGeneralData, sst.methodSampleData,
                #           sst.methodStdData, sst.csvMerged
                #############################################################################
                
                if (len(csvSummaryFile) == 1 and len(normalFile) == 1 and len(quickFile) == 1 and len(standardFile) == 1):    
                    
                    # 4a1. Quantitative Conditions:
                    # - 4a11. "General Information" (quickData -> sst.methodGeneralData)
                    # - 4a12. "Measurement Conditions" (quickData -> sst.methodSampleData)
                    # - 4a13. "Standard Data" (quickData & standardData -> sst.methodStdData)
                    ###########################################################################
                    
                    try:
                        # Elements from quickData (variable needed below)
                        sst.condElements = ['Element', ' '.join(re.findall(r'(?s)Elements\s*?((?!\s*?Condition\s*?)(?!\s*?O\s*?(?:\n|\r\n?)Mode\s*?)\D*?)(?:\n|\r\n?)', quickData)).split()]
                        
                        # 4a11. "General Information"
                        #        -> infos only in quickData
                        #        -> merged to sst.methodGeneralData
                        ##############################################
                        # find values in txts
                        sst.condInfos = ['General Information', 
                            ['Type', re.search(r'Type\s*?:\s*?(.*)(?:\n|\r\n?)', quickData).group(1).strip()] if re.search(r'Type\s*?:\s*?(.*)(?:\n|\r\n?)', quickData) != None else ['Type', ''], 
                            ['Saved Path', re.search(r'Saved Path: (.*)(?:\n|\r\n?)', quickData).group(1).strip()] if re.search(r'Saved Path: (.*)(?:\n|\r\n?)', quickData) != None else ['Saved Path', ''], 
                            ['Project', re.search(r'Project\s*?:\s*?(.*)(?:\n|\r\n?)', quickData).group(1).strip()] if re.search(r'Project\s*?:\s*?(.*)(?:\n|\r\n?)', quickData) != None else ['Project', ''], 
                            ['Comment', re.search(r'Comment\s*?:\s*?(.*)(?:\n|\r\n?)', quickData).group(1).strip()] if re.search(r'Comment\s*?:\s*?(.*)(?:\n|\r\n?)', quickData) != None else ['Comment', ''], 
                            ['Accelerating Voltage (kV)', re.search(r'Accv:\s*?(.*)\s*?kV(?:\n|\r\n?)', quickData).group(1).strip()] if re.search(r'Accv:\s*?(.*)\s*?kV(?:\n|\r\n?)', quickData) != None else ['Accelerating Voltage (kV)', ''], 
                            ['Target Probe Current (nA)', round((float(re.search(r'Target Probe Curr.:\s*?(.*)(?:\n|\r\n?)', quickData).group(1))/float('1.0e-09')),3)] if re.search(r'Target Probe Curr.:\s*?(.*)(?:\n|\r\n?)', quickData) != None else ['Target Probe Current (nA)', ''], 
                            ['Material', re.search(r'Material\s*?:\s*?(.*)(?:\n|\r\n?)', quickData).group(1).strip()] if re.search(r'Material\s*?:\s*?(.*)(?:\n|\r\n?)', quickData) != None else ['Material', ''], 
                            ['Correction Method', re.search(r'Method\s*?:\s*?(.*?)(?:\n|\r\n?)', quickData).group(1).strip()] if re.search(r'Method\s*?:\s*?(.*?)(?:\n|\r\n?)', quickData) != None else ['Correction Method', ''], 
                            ['WDS - EDS', re.search(r'WDS -  EDS\s*?(.*)(?:\n|\r\n?)', quickData).group(1).strip()] if re.search(r'WDS -  EDS\s*?(.*)(?:\n|\r\n?)', quickData) != None else ['WDS - EDS', ''], 
                            ['Peak Search', re.search(r'Peak Search\s*?:\s*?(.*)(?:\n|\r\n?)', quickData).group(1).strip()] if re.search(r'Peak Search\s*?:\s*?(.*)(?:\n|\r\n?)', quickData) != None else ['Peak Search', ''], 
                            ['Bg Measurement', re.search(r'Background Measurement\s*?:\s*?(.*)(?:\n|\r\n?)', quickData).group(1).strip()] if re.search(r'Background Measurement\s*?:\s*?(.*)(?:\n|\r\n?)', quickData) != None else ['Bg Measurement', ''], 
                            ['Measurement', re.search(r'\s*?(.*)\s*?Measurement(?:\n|\r\n?)', quickData).group(1).strip()] if re.search(r'\s*?(.*)\s*?Measurement(?:\n|\r\n?)', quickData) != None else ['Measurement', ''], 
                            ['No. of Positions', re.search(r'No. of Positions\s*?(.*)(?:\n|\r\n?)', quickData).group(1).strip()] if re.search(r'No. of Positions\s*?(.*)(?:\n|\r\n?)', quickData) != None else ['No. of Positions', ''],
                            ['No. of Elements', len(sst.condElements[1])]]
                        
                        # merge to df (sst.methodGeneralData)
                        firstCol = []
                        dataCol = []
                        for i in range(1,len(sst.condInfos)):
                            firstCol.append(sst.condInfos[i][0])
                            dataCol.append(sst.condInfos[i][1])
                        sst.methodGeneralData = pd.DataFrame(data=dataCol, index=firstCol, columns=['Value'])
                        
                        # 4a12. "Measurement Conditions"
                        #        -> infos only in quickData
                        #        -> merged to sst.methodSampleData
                        ############################################## 
                        # find values in txts
                        sst.condSamples = ['Sample',
                            ['X-ray Name', ' '.join(re.findall(r'(?s)X-ray Name\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Signal', [re.search(r'(?s)Standard Condition.*?Signal.*?\s*' + sst.condElements[1][i] + r' \s*(.{3})', quickData).group(1).strip() for i in range(len(sst.condElements[1]))]],
                            ['Order', ' '.join(re.findall(r'(?s)Order\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Channel', ' '.join(re.findall(r'(?s)Channel\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Crystal', ' '.join(re.findall(r'(?s)Crystal\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Spc. Pos. (mm)', ' '.join(re.findall(r'(?s)Spc\.Pos\.\(mm\)\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Bg+ (mm)', ' '.join(re.findall(r'(?s)Back\(\+\) \(mm\)\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Bg- (mm)', ' '.join(re.findall(r'(?s)Back\(\-\) \(mm\)\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Peak Seek W.', ' '.join(re.findall(r'(?s)Peak Seek W\.\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Time/Count', ' '.join(re.findall(r'(?s)Time/Count\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Meas. Time (sec)', ' '.join(re.findall(r'(?s)Mes\.Time\(sec\)\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Bac. Time (sec)', ' '.join(re.findall(r'(?s)Bac\.Time\(sec\)\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Meas. Count', ' '.join(re.findall(r'(?s)Mes\.Count\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Bac. Count', ' '.join(re.findall(r'(?s)Bac\.Count\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['PHA gain', ' '.join(re.findall(r'(?s)PHA gain\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['High V. (V)', ' '.join(re.findall(r'(?s)High V\.\(V\)\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Base L. (V)', ' '.join(re.findall(r'(?s)Base L\.\(V\)\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Window (V)', ' '.join(re.findall(r'(?s)Window \(V\)\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Diff/Int', ' '.join(re.findall(r'(?s)Diff/Int\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Sequence', ' '.join(re.findall(r'(?s)Sequence\s*?(.*?)(?:\n|\r\n?)', quickData)).split()],
                            ['Valence', [re.search(r'(?s)Valence Condition.*?\s*' + sst.condElements[1][i] + r'\( \s*(.*?)\)', quickData).group(1).strip() for i in range(len(sst.condElements[1]))]]]
                        
                        # merge to df (sst.methodSampleData)
                        firstCol = []
                        dataCol = []
                        for i in range(1,len(sst.condSamples)):
                            firstCol.append(sst.condSamples[i][0])
                            dataCol.append(sst.condSamples[i][1])
                        sst.methodSampleData = pd.DataFrame(data=dataCol, index=firstCol, columns=sst.condElements[1])
                        
                        # 4a13. "Standard Data" (in Method Section -> Quant. Conditions -> Full)
                        #        -> infos in quickData & standardData
                        #        -> merged to sst.methodStdData
                        ###########################################################################
                        # find values in txts
                        condStdNames = [re.search(r'(?s)Standard Data.*?(?:\n|\r\n)\s*?' + str(i) + r'\s\S*\s*(.*?)\s', standardData).group(1).strip() for i in range(1,len(sst.condElements[1])+1)] # used below
                        condStdProjects = [re.search(r'(?s)Standard Condition.*?Project.*?\s*' + sst.condElements[1][i] + r'\s*\S{3}\s*' + condStdNames[i] + r'(.*?)\s*\S*(?:\n|\r\n)', quickData).group(1).strip() if re.search(r'(?s)Standard Condition.*?Project.*?\s*' + sst.condElements[1][i] + r'\s*\S{3}\s*' + condStdNames[i] + r'(.*?)\s*\S*(?:\n|\r\n)', quickData) != None else None for i in range(len(sst.condElements[1]))] # used below
                        sst.condStd = ['Standard',
                            ['Std Name', condStdNames],
                            ['Detection Limit (μg/g)', [(str(round(csvSummaryData[sst.condElements[1][i] + '(D.L.)'].median(),2)) + ' ± ' + str(round(csvSummaryData[sst.condElements[1][i] + '(D.L.)'].std(),2))) if (sst.condElements[1][i] + '(D.L.)' in csvSummaryData) else pd.Series('-',name=sst.condElements[1][i] + '(D.L.)') for i in range(len(sst.condElements[1]))]],
                            ['Std Conc (Ox-wt%)', [re.search(r'(?s)Standard Data.*?(?:\n|\r\n)\s*?' + str(i) + r'\s*\S*\s*\S*\s*(.*?)\s', standardData).group(1).strip() if re.search(r'(?s)Standard Data.*?(?:\n|\r\n)\s*?' + str(i) + r'\s*\S*\s*\S*\s*(.*?)\s', standardData) != None else '' for i in range(1,len(sst.condElements[1])+1)]],
                            ['Std Project', condStdProjects],
                            ['Std File', [re.search(r'(?s)Standard Condition.*?Meas.*?\s*' + sst.condElements[1][i] + r'\s*\S{3}\s*' + condStdNames[i] + r'(.*?)(?:\n|\r\n)', quickData).group(1).strip().replace(condStdProjects[i], '').strip() if re.search(r'(?s)Standard Condition.*?Meas.*?\s*' + sst.condElements[1][i] + r'\s*\S{3}\s*' + condStdNames[i] + r'(.*?)(?:\n|\r\n)', quickData) != None else '' for i in range(len(sst.condElements[1]))]],
                            ['Std Current (nA)', [re.search(r'(?s)Curr\.\(A\).*?(?:\n|\r\n)\s*?' + str(i) + r'(?:\s*\S*\s*){1}(.*?)\s', standardData).group(1).strip() if re.search(r'(?s)Curr\.\(A\).*?(?:\n|\r\n)\s*?' + str(i) + r'(?:\s*\S*\s*){1}(.*?)\s', standardData) != None else '' for i in range(1,len(sst.condElements[1])+1)]],
                            ['Std Net (cps)', [re.search(r'(?s)Net\(cps\).*?(?:\n|\r\n)\s*?' + str(i) + r'(?:\s*\S*\s*){2}(.*?)\s', standardData).group(1).strip() if re.search(r'(?s)Net\(cps\).*?(?:\n|\r\n)\s*?' + str(i) + r'(?:\s*\S*\s*){2}(.*?)\s', standardData) != None else '' for i in range(1,len(sst.condElements[1])+1)]],
                            ['Std Bg- (cps)', [re.search(r'(?s)Bg-\(cps\).*?(?:\n|\r\n)\s*?' + str(i) + r'(?:\s*\S*\s*){3}(.*?)\s', standardData).group(1).strip() if re.search(r'(?s)Bg-\(cps\).*?(?:\n|\r\n)\s*?' + str(i) + r'(?:\s*\S*\s*){3}(.*?)\s', standardData) != None else '' for i in range(1,len(sst.condElements[1])+1)]],
                            ['Std Bg+ (cps)', [re.search(r'(?s)Bg\+\(cps\).*?(?:\n|\r\n)\s*?' + str(i) + r'(?:\s*\S*\s*){4}(.*?)\s', standardData).group(1).strip() if re.search(r'(?s)Bg\+\(cps\).*?(?:\n|\r\n)\s*?' + str(i) + r'(?:\s*\S*\s*){4}(.*?)\s', standardData) != None else '' for i in range(1,len(sst.condElements[1])+1)]],
                            ['Std s.d. (%)', [re.search(r'(?s)S\.D\.\(\%\).*?(?:\n|\r\n)\s*?' + str(i) + r'(?:\s*\S*\s*){5}(.*?)\s', standardData).group(1).strip() if re.search(r'(?s)S\.D\.\(\%\).*?(?:\n|\r\n)\s*?' + str(i) + r'(?:\s*\S*\s*){5}(.*?)\s', standardData) != None else '' for i in range(1,len(sst.condElements[1])+1)]],
                            ['Std Datetime', [pd.to_datetime(' '.join(re.search(r'(?s)Date.*?(?:\n|\r\n)\s*?' + str(i) + r'(?:\s*\S*){6}(.*?)\s*?(?:\n|\r\n)', standardData).group(1).strip().split()), format='%Y/%m/%d %H:%M:%S') if re.search(r'(?s)Date.*?(?:\n|\r\n)\s*?' + str(i) + r'(?:\s*\S*){6}(.*?)\s*?(?:\n|\r\n)', standardData) != None else '' for i in range(1,len(sst.condElements[1])+1)]],
                            ['Std f (chi)', [re.search(r'(?s)f\(chi\).*?(?:\n|\r\n)\s*?' + sst.condElements[1][i] + r'(?:\s*)(.*?)\s', standardData).group(1).strip() if re.search(r'(?s)f\(chi\).*?(?:\n|\r\n)\s*?' + sst.condElements[1][i] + r'(?:\s*)(.*?)\s', standardData) != None else '' for i in range(len(sst.condElements[1]))]],
                            ['Std If/Ip', [re.search(r'(?s)If\/Ip.*?(?:\n|\r\n)\s*?' + sst.condElements[1][i] + r'(?:\s*\S*\s*){1}(.*?)\s', standardData).group(1).strip() if re.search(r'(?s)If\/Ip.*?(?:\n|\r\n)\s*?' + sst.condElements[1][i] + r'(?:\s*\S*\s*){1}(.*?)\s', standardData) != None else '' for i in range(len(sst.condElements[1]))]],
                            ['Std abs-el', [re.search(r'(?s)abs-el.*?(?:\n|\r\n)\s*?' + sst.condElements[1][i] + r'(?:\s*\S*\s*){2}(.*?)\s', standardData).group(1).strip() if re.search(r'(?s)abs-el.*?(?:\n|\r\n)\s*?' + sst.condElements[1][i] + r'(?:\s*\S*\s*){2}(.*?)\s', standardData) != None else '' for i in range(len(sst.condElements[1]))]],
                            ['Std 1/s-el', [re.search(r'(?s)1\/s-el.*?(?:\n|\r\n)\s*?' + sst.condElements[1][i] + r'(?:\s*\S*\s*){3}(.*?)\s', standardData).group(1).strip() if re.search(r'(?s)1\/s-el.*?(?:\n|\r\n)\s*?' + sst.condElements[1][i] + r'(?:\s*\S*\s*){3}(.*?)\s', standardData) != None else '' for i in range(len(sst.condElements[1]))]],
                            ['Std r-el', [re.search(r'(?s)r-el.*?(?:\n|\r\n)\s*?' + sst.condElements[1][i] + r'(?:\s*\S*\s*){4}(.*?)\s', standardData).group(1).strip() if re.search(r'(?s)r-el.*?(?:\n|\r\n)\s*?' + sst.condElements[1][i] + r'(?:\s*\S*\s*){4}(.*?)\s', standardData) != None else '' for i in range(len(sst.condElements[1]))]],
                            ['Std c/k-el', [re.search(r'(?s)c\/k-el.*?(?:\n|\r\n)\s*?' + sst.condElements[1][i] + r'(?:\s*\S*\s*){5}(.*?)\s', standardData).group(1).strip() if re.search(r'(?s)c\/k-el.*?(?:\n|\r\n)\s*?' + sst.condElements[1][i] + r'(?:\s*\S*\s*){5}(.*?)\s', standardData) != None else '' for i in range(len(sst.condElements[1]))]]]
                        
                        # merge to df (sst.methodStdData)
                        firstCol = []
                        dataCol = []
                        for i in range(1,len(sst.condStd)):
                            firstCol.append(sst.condStd[i][0])
                            dataCol.append(sst.condStd[i][1])
                        sst.methodStdData = pd.DataFrame(data=dataCol, index=firstCol, columns=sst.condElements[1])
                        
                    except:
                        st.error('An error occurred while merging your ' + quickName + '-file and ' + standardName + '-file, please check them and try again.', icon=':material/sync_problem:')
                        kadiStatus.update(label='Something went wrong, please read the corresponding error message for details.', state='error', expanded=True)
                        kadiError = True
                        st.stop()


                    # 4a2. "Quantitative Data" table (in Data Filter):
                    #      merge data from csvSummaryData & normalData -> sst.csvMerged
                    #      - csvSummaryData: all measurements
                    #      - normalData: comment, datetimes, diameters
                    #      --> merge both on comment
                    #######################################################################
                    
                    try:                           
                        mergeCsvNormal = pd.merge(csvSummaryData, normalData, on='Comment', validate='one_to_one')
                        
                        # delete unneeded columns
                        k = ['Norm%', 'mole%', 'K-ratio', 'K-raw', 'Net', 'BG-', 'BG+', 'L-value', 'Error%', 'D.L.', 'Unnamed'] # by keyword
                        for key in k:
                            mergeCsvNormal = mergeCsvNormal[mergeCsvNormal.columns.drop(list(mergeCsvNormal.filter(regex=key)))]
                        # drop column header
                        mergeCsvNormal = mergeCsvNormal.drop(columns=mergeCsvNormal.columns[mergeCsvNormal.columns == ' '])
                        # set index to Point ###################Comment (-> rename to Sample Name)
                        mergeCsvNormal = mergeCsvNormal.set_index('Point')#.rename_axis('Sample Name')
                        # rename some headers
                        mergeCsvNormal.columns = mergeCsvNormal.columns.str.replace('Mass%', 'wt%').str.replace('Cation', 'cat/24ox').str.replace('(', ' (').str.replace('Comment', 'Sample Name')
                        # save in sst
                        sst.csvMerged = mergeCsvNormal
                    except:
                        st.error('An error occurred while merging your ' + csvSummaryName + '-file and ' + normalName + '-file, please check them and try again.', icon=':material/sync_problem:')
                        kadiStatus.update(label='Something went wrong, please read the corresponding error message for details.', state='error', expanded=True)
                        kadiError = True
                        st.stop()
                    
                    
                    # 4a3. "Compact Measurement Conditions" -> sst.shortMeasCond
                    #      merge data from above:
                    #      - sst.methodGeneralData
                    #      - sst.methodSampleData
                    #      - sst.methodStdData
                    #      - sst.csvMerged
                    ###############################################################
                    
                    try:
                        # methodData
                        shortMeasCond0 = sst.methodGeneralData.loc[['Accelerating Voltage (kV)', 'Target Probe Current (nA)'], :]                    
                        # csvData
                        shortMeasCond0.loc['Spotsizes used (μm)'] = ', '.join(map(str, sorted(sst.csvMerged['Spotsize'].unique())))                    
                        
                        # Messtabelle
                        ## Element name
                        shortMeasCond1 = pd.DataFrame([sst.methodSampleData.columns.tolist()], columns=sst.methodSampleData.columns, index=['Element'])
                        
                        ## Crystal, Meas time
                        shortMeasCond2 = sst.methodSampleData.loc[['Crystal', 'Meas. Time (sec)'], :]
                        
                        ## Std Name, Detection Limit
                        shortMeasCond3 = sst.methodStdData.loc[['Std Name', 'Detection Limit (μg/g)'], :]
                        shortMeasCond = pd.concat([shortMeasCond1, shortMeasCond2, shortMeasCond3]).transpose()
                        sst.shortMeasCond[0] = shortMeasCond0
                        sst.shortMeasCond[1] = shortMeasCond                    
                    
                    except:
                        st.error('An error occurred while merging your ' + csvSummaryName + '-file and ' + quickName + '-file, please check them and try again.', icon=':material/sync_problem:')
                        kadiStatus.update(label='Something went wrong, please read the corresponding error message for details.', state='error', expanded=True)
                        kadiError = True
                        st.stop()
                
                
                # 4b. QUALITATIVE SPECTRA
                # - 4b1. "General Information" (qualiSpectraQuickData -> sst.methodQualiGeneralData)
                # - 4b2. "Spectrometer Conditions" (qualiSpectraQuickData -> sst.methodQualiSpecData)
                ##########################################################################################
                
                if len(qualiSpectraQuickFile) == 1:
                    
                    try:
                        # 4b1. "General Information"
                        #        -> infos in qualiSpectraQuickData
                        #        -> merged to sst.methodQualiGeneralData
                        ####################################################
                        
                        # find values in txt
                        sst.qualiConditions = ['General Information', 
                            ['Type', re.search(r'Type\s*?:\s*?(.*)(?:\n|\r\n?)', qualiSpectraQuickData).group(1).strip()] if re.search(r'Type\s*?:\s*?(.*)(?:\n|\r\n?)', qualiSpectraQuickData) != None else ['Type', ''], 
                            ['Saved Path', re.search(r'Saved Path: (.*)(?:\n|\r\n?)', qualiSpectraQuickData).group(1).strip()] if re.search(r'Saved Path: (.*)(?:\n|\r\n?)', qualiSpectraQuickData) != None else ['Saved Path', ''], 
                            ['Project', re.search(r'Project\s*?:\s*?(.*)(?:\n|\r\n?)', qualiSpectraQuickData).group(1).strip()] if re.search(r'Project\s*?:\s*?(.*)(?:\n|\r\n?)', qualiSpectraQuickData) != None else ['Project', ''], 
                            ['Comment', re.search(r'Comment\s*?:\s*?(.*)(?:\n|\r\n?)', qualiSpectraQuickData).group(1).strip()] if re.search(r'Comment\s*?:\s*?(.*)(?:\n|\r\n?)', qualiSpectraQuickData) != None else ['Comment', ''], 
                            ['Accelerating Voltage (kV)', re.search(r'Accv:\s*?(.*)\s*?kV(?:\n|\r\n?)', qualiSpectraQuickData).group(1).strip()] if re.search(r'Accv:\s*?(.*)\s*?kV(?:\n|\r\n?)', qualiSpectraQuickData) != None else ['Accelerating Voltage (kV)', ''],
                            ['Target Probe Current (nA)', round((float(re.search(r'Target Probe Curr.:\s*?(.*)(?:\n|\r\n?)', qualiSpectraQuickData).group(1))/float('1.0e-09')),3)] if re.search(r'Target Probe Curr.:\s*?(.*)(?:\n|\r\n?)', qualiSpectraQuickData) != None else ['Target Probe Current (nA)', ''],
                            ['No. of Positions', re.search(r'No. of Positions\s*?(.*)(?:\n|\r\n?)', qualiSpectraQuickData).group(1).strip()] if re.search(r'No. of Positions\s*?(.*)(?:\n|\r\n?)', qualiSpectraQuickData) != None else ['No. of Positions', ''],
                            ['No. of Spectra', re.search(r'No. of Spect =\s*?(.*)(?:\n|\r\n?)', qualiSpectraQuickData).group(1).strip()] if re.search(r'No. of Spect =\s*?(.*)(?:\n|\r\n?)', qualiSpectraQuickData) != None else ['No. of Spectra', '']
                            ]
                        
                        # merge to df (sst.methodQualiGeneralData)
                        firstCol = []
                        dataCol = []
                        for i in range(1,len(sst.qualiConditions)):
                            firstCol.append(sst.qualiConditions[i][0])
                            dataCol.append(sst.qualiConditions[i][1])
                        sst.methodQualiGeneralData = pd.DataFrame(data=dataCol, index=firstCol, columns=['Value'])
                        
                        # 4b2. "Spectrometer Conditions"
                        #        -> infos in qualiSpectraQuickData
                        #        -> merged to sst.methodQualiSpecData
                        ####################################################
                        
                        # find values in txt
                        sst.qualiSpectra = ['Spectrometer Conditions',
                            ['Channel', ' '.join(re.findall(r'(?s)Channel\s*?(.*?)(?:\n|\r\n?)', qualiSpectraQuickData)).split()],
                            ['Crystal', ' '.join(re.findall(r'(?s)Crystal\s*?(.*?)(?:\n|\r\n?)', qualiSpectraQuickData)).split()],
                            ['Start (mm)', ' '.join(re.findall(r'(?s)Start\s*?\(mm\)\s*?(.*?)(?:\n|\r\n?)', qualiSpectraQuickData)).split()],
                            ['End (mm)', ' '.join(re.findall(r'(?s)End\s*?\(mm\)\s*?(.*?)(?:\n|\r\n?)', qualiSpectraQuickData)).split()],
                            ['Dwell time (ms)', ' '.join(re.findall(r'(?s)Dwell\s*?\(ms\)\s*?(.*?)(?:\n|\r\n?)', qualiSpectraQuickData)).split()],
                            ['PHA gain', ' '.join(re.findall(r'(?s)PHA Gain\s*?(.*?)(?:\n|\r\n?)', qualiSpectraQuickData)).split()],
                            ['High V. (V)', ' '.join(re.findall(r'(?s)High V\.\(V\)\s*?(.*?)(?:\n|\r\n?)', qualiSpectraQuickData)).split()],
                            ['Base L. (V)', ' '.join(re.findall(r'(?s)Base L\.\(V\)\s*?(.*?)(?:\n|\r\n?)', qualiSpectraQuickData)).split()],
                            ['Window (V)', ' '.join(re.findall(r'(?s)Window \(V\)\s*?(.*?)(?:\n|\r\n?)', qualiSpectraQuickData)).split()],
                            ['Diff/Int', ' '.join(re.findall(r'(?s)Diff/Int\s*?(.*?)(?=\r?\n|$)', qualiSpectraQuickData)).split()]
                            ]

                        
                        
                        # merge to df (sst.methodQualiSpecData)
                        firstCol = []
                        dataCol = []
                        for i in range(1,len(sst.qualiSpectra)):
                            firstCol.append(sst.qualiSpectra[i][0])
                            dataCol.append(sst.qualiSpectra[i][1])
                            
                        sst.methodQualiSpecData = pd.DataFrame(data=dataCol, index=firstCol, columns=[f"Spec. {i}" for i in range(1, int(re.search(r'No. of Spect =\s*?(.*)(?:\n|\r\n?)', qualiSpectraQuickData).group(1).strip()) + 1)])

                        
                    except:
                        st.error('An error occurred while merging data from your ' + qualiSpectraQuickName + '-file, please check them and try again.', icon=':material/sync_problem:')
                        kadiStatus.update(label='Something went wrong, please read the corresponding error message for details.', state='error', expanded=True)
                        kadiError = True
                        st.stop()
                
                
                # 4c. MAPS ONLY
                # -> infos in json
                ####################################################
                
                if sst.importMaps:
                    if len(mapFiles) > 0 and len(mapJsonsData) > 0:
                    
                        # 4c1. Map Conditions:
                        # - 4c11. "General Parameters" (mapJsonsData -> sst.mapGeneralData)
                        # - 4c12. "WDS Measurement Conditions" (mapJsonsData -> sst.mapWdsData)
                        # - 4c13. "EDS Measurement Conditions" (mapJsonsData -> sst.mapEdsData)
                        ###########################################################################
                        
                        try:                   
                            # for every map
                            for mapNameJson in mapJsonsData.keys():
                            
                                # 4c11. "General Information"
                                #        -> infos in mapJsonsData
                                #        -> merged to sst.mapGeneralData for map
                                #########################################################

                                # get data from jsons
                                mapGeneral = [ 
                                    ['Saved Path', mapJsonsData[mapNameJson]['general parameters']['save path']] if 'save path' in mapJsonsData[mapNameJson]['general parameters'] else ['Saved Path', ''], 
                                    ['Project', mapJsonsData[mapNameJson]['general parameters']['project name']] if 'project name' in mapJsonsData[mapNameJson]['general parameters'] else ['Project', ''], 
                                    ['Sample Name', mapJsonsData[mapNameJson]['general parameters']['sample name']] if 'sample name' in mapJsonsData[mapNameJson]['general parameters'] else ['Sample Name', ''],
                                    ['Date', mapJsonsData[mapNameJson]['general parameters']['date']] if 'date' in mapJsonsData[mapNameJson]['general parameters'] else ['Date', ''],
                                    ['Accelerating Voltage (kV)', mapJsonsData[mapNameJson]['general parameters']['accelerating voltage (kV)']] if 'accelerating voltage (kV)' in mapJsonsData[mapNameJson]['general parameters'] else ['Accelerating Voltage (kV)', ''], 
                                    ['Target Probe Current (nA)', round((float(mapJsonsData[mapNameJson]['general parameters']['target probe current (nA)'])/float('1.0e-09')),3)] if 'target probe current (nA)' in mapJsonsData[mapNameJson]['general parameters'] else ['Target Probe Current (nA)', ''], 
                                    ['Probe Current (nA)', round((float(mapJsonsData[mapNameJson]['general parameters']['probe current (nA)'])/float('1.0e-09')),3)] if 'probe current (nA)' in mapJsonsData[mapNameJson]['general parameters'] else ['Probe Current (nA)', ''], 
                                    ['Probe Diameter (µm)', mapJsonsData[mapNameJson]['general parameters']['probe diameter (µm)']] if 'probe diameter (µm)' in mapJsonsData[mapNameJson]['general parameters'] else ['Probe Diameter (µm)', ''], 
                                    ['Dwell Time (ms)', mapJsonsData[mapNameJson]['general parameters']['dwell time (ms)']] if 'dwell time (ms)' in mapJsonsData[mapNameJson]['general parameters'] else ['Dwell Time (ms)', ''], 
                                    ['No. of Pixels (x | y)', mapJsonsData[mapNameJson]['general parameters']['number of pixels: x, y'].replace(' ', ' | ')] if 'number of pixels: x, y' in mapJsonsData[mapNameJson]['general parameters'] else ['No. of Pixels (x | y)', ''], 
                                    ['Pixel Size (µm) (x | y)', ' '.join(mapJsonsData[mapNameJson]['general parameters']['pixel size: x, y (µm)'].split()[:2]).replace(' ', ' | ')] if 'pixel size: x, y (µm)' in mapJsonsData[mapNameJson]['general parameters'] else ['Pixel Size (x | y)', ''], 
                                    ['Stage Position (mm): Center (x | y | z)', mapJsonsData[mapNameJson]['general parameters']['stage position center (mm)'].replace(' ', ' | ')] if 'stage position center (mm)' in mapJsonsData[mapNameJson]['general parameters'] else ['Stage Position (mm): Center (x | y | z)', ''], 
                                    ['Stage Position (mm): Upper left (x | y | z)', mapJsonsData[mapNameJson]['general parameters']['stage position upper left (mm)'].replace(' ', ' | ')] if 'stage position upper left (mm)' in mapJsonsData[mapNameJson]['general parameters'] else ['Stage Position (mm): Upper left (x | y | z)', ''],  
                                    ['Stage Position (mm): Upper right (x | y | z)', mapJsonsData[mapNameJson]['general parameters']['stage position upper right (mm)'].replace(' ', ' | ')] if 'stage position upper right (mm)' in mapJsonsData[mapNameJson]['general parameters'] else ['Stage Position (mm): Upper right (x | y | z)', ''],  
                                    ['Stage Position (mm): Lower right (x | y | z)', mapJsonsData[mapNameJson]['general parameters']['stage position lower right (mm)'].replace(' ', ' | ')] if 'stage position lower right (mm)' in mapJsonsData[mapNameJson]['general parameters'] else ['Stage Position (mm): Lower right (x | y | z)', ''],  
                                    ['Stage Position (mm): Lower left (x | y | z)', mapJsonsData[mapNameJson]['general parameters']['stage position lower left (mm)'].replace(' ', ' | ')] if 'stage position lower left (mm)' in mapJsonsData[mapNameJson]['general parameters'] else ['Stage Position (mm): Lower left (x | y | z)', ''], 
                                    ['WDS Elements', ', '.join(sorted(mapJsonsData[mapNameJson]['general parameters']['wds elements']))] if 'wds elements' in mapJsonsData[mapNameJson]['general parameters'] else ['WDS Elements', ''], 
                                    ['EDS Elements', ', '.join(sorted(mapJsonsData[mapNameJson]['general parameters']['eds elements']))] if 'eds elements' in mapJsonsData[mapNameJson]['general parameters'] else ['EDS Elements', '']
                                ]
                                
                                # merge to df
                                firstCol = []
                                dataCol = []
                                for i in range(0,len(mapGeneral)):
                                    firstCol.append(mapGeneral[i][0])
                                    dataCol.append(mapGeneral[i][1])
                                sst.mapGeneralData[mapNameJson] = pd.DataFrame(data=dataCol, index=firstCol, columns=['Value'])
                        
                                # 4c12. "WDS Measurement Conditions"
                                #        -> infos in mapJsonsData
                                #        -> merged to sst.mapWdsData for map
                                #####################################################
                            
                                # get data from jsons if there are wds elements
                                if 'wds elements' in mapJsonsData[mapNameJson]['general parameters']:

                                    # get wds elements
                                    wdsElements = sorted(mapJsonsData[mapNameJson]['general parameters']['wds elements'])
                                    
                                    # get wds data
                                    mapWDS = [
                                        ['Characteristic Line', [mapJsonsData[mapNameJson]['element specific parameters'][element]['characteristic line'] if 'characteristic line' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['Characteristic Line', ''] for element in wdsElements]],
                                        ['Order', [mapJsonsData[mapNameJson]['element specific parameters'][element]['order'] if 'order' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['Order', ''] for element in wdsElements]],
                                        ['Analyser Crystal', [mapJsonsData[mapNameJson]['element specific parameters'][element]['analyser crystal'] if 'analyser crystal' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['Analyser Crystal', ''] for element in wdsElements]],
                                        ['PHA Mode', [mapJsonsData[mapNameJson]['element specific parameters'][element]['PHA mode'] if 'PHA mode' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['PHA Mode', ''] for element in wdsElements]],
                                        ['PHA Gain', [mapJsonsData[mapNameJson]['element specific parameters'][element]['PHA gain'] if 'PHA gain' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['PHA Gain', ''] for element in wdsElements]],
                                        ['PHA Base Level (V)', [mapJsonsData[mapNameJson]['element specific parameters'][element]['PHA base level (V)'] if 'PHA base level (V)' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['PHA Base Level (V)', ''] for element in wdsElements]],
                                        ['PHA Window (V)', [mapJsonsData[mapNameJson]['element specific parameters'][element]['PHA window (V)'] if 'PHA window (V)' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['PHA Window (V)', ''] for element in wdsElements]],
                                        ['Detector High V. (V)', [mapJsonsData[mapNameJson]['element specific parameters'][element]['detector HV (V)'] if 'detector HV (V)' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['Detector High V. (V)', ''] for element in wdsElements]],
                                        ['Sequence', [mapJsonsData[mapNameJson]['element specific parameters'][element]['sequence'] if 'sequence' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['Sequence', ''] for element in wdsElements]],
                                        ['Spectrometer', [mapJsonsData[mapNameJson]['element specific parameters'][element]['spectrometer'] if 'spectrometer' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['Spectrometer', ''] for element in wdsElements]],
                                        ['Spectrometer radius (mm)', [mapJsonsData[mapNameJson]['element specific parameters'][element]['spectrometer radius (mm)'] if 'spectrometer radius (mm)' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['Spectrometer radius (mm)', ''] for element in wdsElements]],
                                        ['Peak (mm)', [mapJsonsData[mapNameJson]['element specific parameters'][element]['peak (mm)'] if 'peak (mm)' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['Peak (mm)', ''] for element in wdsElements]]
                                    ]
                                    
                                    # merge to df
                                    firstCol = []
                                    dataCol = []
                                    for i in range(0,len(mapWDS)):
                                        firstCol.append(mapWDS[i][0])
                                        dataCol.append(mapWDS[i][1])
                                    sst.mapWdsData[mapNameJson] = pd.DataFrame(data=dataCol, index=firstCol, columns=wdsElements)
                                    
                                # 4c13. "EDS Measurement Conditions"
                                #        -> infos in mapJsonsData
                                #        -> merged to sst.mapEdsData for map
                                #####################################################
                                
                                # get data from jsons if there are eds elements
                                if 'eds elements' in mapJsonsData[mapNameJson]['general parameters']:
                                
                                    # get eds elements
                                    edsElements = sorted(mapJsonsData[mapNameJson]['general parameters']['eds elements'])
                                    
                                    # get eds data
                                    mapEDS = [
                                        ['Characteristic Line', [mapJsonsData[mapNameJson]['element specific parameters'][element]['characteristic line'] if 'characteristic line' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['Characteristic Line', ''] for element in edsElements]],
                                        ['ROI Start (keV)', [mapJsonsData[mapNameJson]['element specific parameters'][element]['ROI start (keV)'] if 'ROI start (keV)' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['ROI Start (keV)', ''] for element in edsElements]],
                                        ['ROI End (keV)', [mapJsonsData[mapNameJson]['element specific parameters'][element]['ROI end (keV)'] if 'ROI end (keV)' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['ROI End (keV)', ''] for element in edsElements]],
                                        ['Sequence', [mapJsonsData[mapNameJson]['element specific parameters'][element]['sequence'] if 'sequence' in mapJsonsData[mapNameJson]['element specific parameters'][element] else ['Sequence', ''] for element in edsElements]]
                                    ]
                                    
                                    ## merge to df
                                    firstCol = []
                                    dataCol = []
                                    for i in range(0,len(mapEDS)):
                                        firstCol.append(mapEDS[i][0])
                                        dataCol.append(mapEDS[i][1])
                                    sst.mapEdsData[mapNameJson] = pd.DataFrame(data=dataCol, index=firstCol, columns=edsElements)
                    
                        except:
                            st.error('An error occurred while processing your ' + mapJsonName + '-file(s), please check them and try again.', icon=':material/sync_problem:')
                            kadiStatus.update(label='Something went wrong, please read the corresponding error message for details.', state='error', expanded=True)
                            kadiError = True
                            st.stop()
                    
                    
                ###########################################
                # 5. load saved filter settings from kadi
                ###########################################
                    
                # 5a. QUANT (or MAPS + QUANT)
                #     -> Data filter settings for Quantitative Data table
                ###########################################################

                if len(kadiFilter) > 0:
                    
                    st.write(':material/cloud_download: Loading saved data filter settings ...')
                    
                    for i, filterID in enumerate(kadiFilter.keys()):
                        data = json.loads(kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + filterID + '/download'))
                        sst.kadiFilter[data['updateTime']] = data
                
                # 5b. MAPS ONLY
                #     -> Map display settings for Element Maps
                ################################################
                
                if sst.importMaps:
                    if len(mapFilter) > 0:
                        
                        st.write(':material/cloud_download: Loading saved map settings ...')
                        
                        for i, filterID in enumerate(mapFilter.keys()):
                            data = json.loads(kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + filterID + '/download'))
                            sst.mapFilter[data['updateTime']] = data


                #######################
                # 6. load map files 
                #######################
                
                if sst.importMaps:
                    if len(mapFiles) > 0:
                        # loading progress bar
                        mapsLoaded = 0
                        sst.mapData = {}
                        progressTxt = ':material/cloud_download: Loading map data files, this may take a while ... (' + str(mapsLoaded) + '/' + str(len(mapFiles)) + ' loaded)'
                        mapProgress = st.progress(0, text=progressTxt)
                        for mapId in mapFiles.keys():
                            parts = mapFiles[mapId].rstrip('.csv').split(' ')
                            # check length of parts (3 = COMPO, 5 = other)
                            if len(parts) != 5 and len(parts) != 3:
                                st.error('Wrong format for map: ' + str(mapFiles[mapId]) + '. Please contact us via mail (see ' + fn.pageNames['help']['ico'] + ' **' + fn.pageNames['help']['name'] + '**).', icon=':material/sync_problem:')
                                time.sleep(2)
                            else:
                                sst.mapData[mapFiles[mapId]] = {
                                                                'sample': str(parts[1]),
                                                                'type': str(parts[2]), # EDS, WDS, COMPO
                                                                'element': (parts[3] if len(parts) > 3 else ''), # not in COMPO
                                                                'characteristicLine': (parts[4] if len(parts) > 3 else ''), # Ka, La # not in COMPO
                                                                'imgData': pd.read_csv(
                                                                        io.StringIO(kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + mapId + '/download').decode('utf_8')), header=None, index_col=False, engine='python'
                                                                        ),
                                                                }
                            
                            mapsLoaded = mapsLoaded + 1
                            progressTxt = ':material/cloud_download: Loading map data files, this may take a while ... (' + str(mapsLoaded) + '/' + str(len(mapFiles)) + ' loaded)'                                    
                            mapPercent = (100/len(mapFiles)*mapsLoaded)/100
                            mapProgress.progress(mapPercent, text=progressTxt)
                else:
                    st.write(':material/skip_next: Skipping element map import.')
                

                ########################
                # 7. load image files 
                ########################
                
                if sst.importImages:
                    if len(imageFiles) >= 0:
                        # loading progress bar
                        imgLoaded = 0
                        progressTxt = ':material/cloud_download: Loading image data, this may take a while ... (' + str(imgLoaded) + '/' + str(len(imageFiles)) + ' loaded)'
                        imgProgress = st.progress(0, text=progressTxt)
                        for imageId in imageFiles.keys():
                            if '.tif' in imageFiles[imageId] or '.tiff' in imageFiles[imageId]:
                                sst.imageData = sst.imageData + [[imageId, tiff.imread(io.BytesIO(kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + imageId + '/download')))]]
                            elif '.jpg' in imageFiles[imageId] or '.jpeg' in imageFiles[imageId]:
                                sst.imageData = sst.imageData + [[imageId, Image.open(io.BytesIO(kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + imageId + '/download')))]]
                            
                            imgLoaded = imgLoaded + 1
                            progressTxt = ':material/cloud_download: Loading image data, this may take a while ... (' + str(imgLoaded) + '/' + str(len(imageFiles)) + ' loaded)'                                    
                            imgPercent = (100/len(imageFiles)*imgLoaded)/100
                            imgProgress.progress(imgPercent, text=progressTxt)
                        sst.imageFiles = imageFiles
                else:
                    st.write(':material/skip_next: Skipping image import.')
                
                
                ################
                # 8. Success
                ################
                
                # re-check for errors in case st.stop() doesn't work
                if not kadiError:
                    sst.kadiLoaded = True
                    st.toast('Files successfully uploaded', icon=':material/cloud_done:')
                    kadiStatus.update(label='Download complete!', state='complete', expanded=True)
                    # clear form container if successful
                    if parentContainer:
                        parentContainer.empty()
                    sst.infoToast['txt'] = 'Record successfully loaded.'
                    sst.infoToast['ico'] = ':material/data_check:'
                    st.switch_page('pages/data-viewer.py')
                    
        except KeyError:
            # 403 Error: Forbidden
            if 'code' in response.json() and response.json()['code'] == 403:
                st.error('You don\'t have the permission to access [**this record**&thinsp;:link:](https://kadi4mat.iam.kit.edu/records/' + str(sst.recordID) + '?tab=files). It is either read-protected or not readable by the server.', icon=':material/vpn_key_alert:')
                sst.recordID = ''
                st.stop()


# get content from kadi file
@st.cache_data(show_spinner=False)
def kadiLoadFile(url):
    if sst.kadiPAT == '':
        authPAT = st.secrets['kadiPAT']
    else:
        authPAT = sst.kadiPAT
    response = requests.get(url, headers={'Authorization': 'Bearer ' + authPAT})
    content = response._content
    return content


# get content from kadi img file
@st.cache_data(show_spinner=False)
def kadiLoadImg(url):
    if sst.kadiPAT == '':
        authPAT = st.secrets['kadiPAT']
    else:
        authPAT = sst.kadiPAT
    response = requests.get(url, headers={'Authorization': 'Bearer ' + authPAT}, allow_redirects=False)
    return response


# upload filters to kadi
def kadiUploadFilters(parentContainer, uploadType):
    parentContainer.empty()
    with parentContainer.container():
        with st.status('Uploading filter settings to Kadi4Mat, please wait ...', expanded = True) as kadiUploadStatus:   
            st.write(':material/cloud_sync: Connecting ...')
            url = 'https://kadi4mat.iam.kit.edu/api/records/' + str(int(sst.recordID)) + '/uploads'
            if sst.kadiPAT == '':
                authPAT = st.secrets['kadiPAT']
            else:
                authPAT = sst.kadiPAT
            headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authPAT}
            if uploadType == 'data':
                metadata = {'name': 'filter_' + sst.dataViewerFilter['updateTime'] + '.txt', 'size': len(json.dumps(sst.dataViewerFilter))}
            else:
                metadata = {'name': 'mapSettings_' + sst.mapEditFilter['updateTime'] + '.txt', 'size': len(json.dumps(sst.mapEditFilter))}
                
            # start upload process
            response = requests.post(url, headers=headers, json=metadata)
            
            if response.status_code == 201:
                st.write(':material/cloud_upload: Starting upload progress ...')
                uploadResponse = response.json()
                uploadID = uploadResponse['id']
                uploadURL = uploadResponse['_actions']['upload_data']
                if uploadType == 'data':
                    uploadData = json.dumps(sst.dataViewerFilter)
                else:
                    uploadData = json.dumps(sst.mapEditFilter)
                uploadHeaders = {'Content-Type': 'application/octet-stream', 'Authorization': 'Bearer ' + authPAT}
                # send data content
                response = requests.put(uploadURL, headers=uploadHeaders, data=uploadData)
                
                if response.status_code == 200 or response.status_code == 201:
                    if uploadType == 'data':
                        st.success('Filter successfully uploaded.', icon=':material/cloud_done:')
                        kadiUploadStatus.update(label='Filter successfully uploaded.', state='complete')
                    else:
                        st.success('Map settings successfully uploaded.', icon=':material/cloud_done:')
                        kadiUploadStatus.update(label='Map settings successfully uploaded.', state='complete')
                else:
                    st.error('Upload failed (' + str(response.reason) + ').', icon=':material/sync_problem:')
                    kadiUploadStatus.update(label='Upload failed (' + str(response.reason) + ').', state='error')
            else:
                if response.status_code == 409:
                    if uploadType == 'data':
                        st.error('Filter already uploaded!', icon=':material/cloud_done:')
                        kadiUploadStatus.update(label='Filter already uploaded!', state='error')
                    else:
                        st.error('Map settings already uploaded!', icon=':material/cloud_done:')
                        kadiUploadStatus.update(label='Map settings already uploaded!', state='error')
                else:
                    st.error('Upload failed (' + str(response.reason) + ').', icon=':material/sync_problem:')
                    kadiUploadStatus.update(label='Upload failed ( ' + str(response.reason) + ').', state='error')
    return