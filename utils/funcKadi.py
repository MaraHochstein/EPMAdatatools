#######################
# imports
#######################
from utils.imports import (st, sst, requests, urllib, datetime, pd, io, re, os, io, re, os, Image, tiff, annotated_text, key, base64, imagecodecs, html, copy, alt, np, go)
import utils.func as fn

import json

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
    with st.spinner('Loading records from profile, please wait...'):
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
    with st.spinner('Loading records from IfG GUF, please wait...'):
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
                        valueWithUnit = '-'
                    else:
                        valueWithUnit = str(response.json()[i]['value'])
                    if 'unit' in response.json()[i]:
                        valueWithUnit = valueWithUnit + ' ' + str(response.json()[i]['unit'])
                    dataCol.append(valueWithUnit)
    
    sst.kadiMetaData = pd.DataFrame(data=dataCol, index=firstCol, columns=['Value'])              


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
                sstVars = 'kadiMetaData', 'condElements', 'condInfos', 'condSamples', 'condStd', 'methodGeneralData', 'methodSampleData', 'methodStdData', 'csvMerged', 'imageData', 'imageFiles', 'kadiLoaded', 'shortMeasCond', 'kadiFilter', 'mapData'
                for var in sstVars:
                    fn.resetVar(var)

                # temp variables(raw filenames & data)
                csvSummaryFile = {}
                csvSummaryData = pd.DataFrame()
                csvSummaryName = 'summary[timestamp].csv'
                
                normalFile = {}
                normalData = ''
                normalName = 'normal.txt'
                
                quickFile = {}
                quickData = ''
                quickName = 'quick standard.txt'
                
                standardFile = {}
                standardData = ''
                standardName = 'summary standard.txt'
                
                kadiError = False
                kadiFilter = {}
                
                imageFiles = {}
                
                mapFiles = {}
                
                # get kadi metadata for record
                st.write('Getting metadata from Kadi4Mat ...')
                kadiGetMetadata()
                
                
                ##########################################
                # 1. get file ids from record
                #    & check if all raw files were found
                ##########################################
                
                # get all filenames from api
                st.write('Checking files for raw EPMA data ...')
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
                        # images
                        elif item['mimetype'] == 'image/tiff' or item['mimetype'] == 'image/jpeg':
                            imageFiles[item['id']] = item['name']
                        # filter
                        elif 'filter' in item['name'] and item['mimetype'] == 'text/plain':
                            kadiFilter[item['id']] = item['name']
                        # maps
                        elif 'map ' in item['name'] and item['mimetype'] == 'text/csv':
                            mapFiles[item['id']] = item['name']
                            
                
                #######################
                #
                #    QUANTITATIVE
                #
                #######################
                # load quant data also for map records if all needed raw files are found:
                if (len(mapFiles) > 0 and len(csvSummaryFile) == 1 and len(normalFile) == 1 and len(quickFile) == 1 and len(standardFile) == 1) or (len(mapFiles) == 0):

                    # check if all needed raw files are found
                    # (this check is already done for map records)
                    missingFiles = []
                    doubleFiles = []
                    doubleFileNames = []
                    
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
                    
                    # show message with missing files
                    if len(missingFiles) > 0:
                        line1 = (('Please upload the following files to [**this record**&thinsp;:link:](https://kadi4mat.iam.kit.edu/records/') if len(missingFiles) > 1 else ('Please upload the following file to [**this record**&thinsp;:link:](https://kadi4mat.iam.kit.edu/records/')) + str(sst.recordID) + '?tab=files) and try again'
                        line2 = '\n' + '\n'.join([f'- {file}' for file in missingFiles])
                        st.error(f'''
                            {line1}
                            {line2}
                            ''', icon=':material/sync_problem:')
                    
                    # show message with double files
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
                    
                    ##################################
                    # 2. load content of raw files
                    #    & check if all contain data
                    ##################################
                    st.write('Loading raw EPMA data ...')
                    invalidFiles = []
                    
                    # load csv-file
                    #################
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
                    else:
                        invalidFiles.append(csvSummaryName + '-file')
                        
                    # load normal-file 
                    ####################
                    content = kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + list(normalFile.keys())[0] + '/download').decode('utf_8')            
                    if len(content) > 2: # text-file contains something
                        normalData = content
                        # find values in text
                        positions = re.findall(r'Position\sNo\.\s*:\s*(\d+)', normalData)
                        datetimes = re.findall(r'Dated\son\s(\d{4}\/\d{2}\/\d{2}\s\d{2}:\d{2}:\d{2})', normalData)
                        diameters = re.findall(r'Probe\sDia.\s*:\s*(\d+\.\d+)', normalData)

                        # combine
                        df = pd.DataFrame(data=({'Point': positions, 'Datetime': pd.to_datetime(datetimes, format='%Y/%m/%d %H:%M:%S'), 'Spotsize': [int(float(x)) for x in  diameters]}))
                        df['Point'] = df['Point'].astype(int)
                        
                        # drop duplicates which may be in original normal-file
                        df = df.drop_duplicates(subset='Point')
                    else:
                        invalidFiles.append(normalName + '-file')  

                    # load quick-file
                    ###################
                    content = kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + list(quickFile.keys())[0] + '/download').decode('utf_8')            
                    if len(content) > 2: # text-file contains something
                        quickData = content
                    else:
                        invalidFiles.append(quickName + '-file')
                    
                    # load standard summary-file
                    ##############################
                    content = kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + list(standardFile.keys())[0] + '/download').decode('utf_8')            
                    if len(content) > 2: # text-file contains something
                        standardData = content
                    else:
                        invalidFiles.append(standardName + '-file')  
                    
                    # check if all raw files contain data for merging
                    ###################################################
                    if len(invalidFiles) > 0:
                        st.error(('The following files contain invalid data, please check them and try again:') if len(invalidFiles) > 1 else ('The following file contains invalid data, please check the data and try again:') + ', '.join(invalidFiles) + '.', icon=':material/sync_problem:')
                        kadiStatus.update(label='Invalid file data, please read the corresponding error message for details.', state='error', expanded=True)
                        kadiError = True
                        st.stop()

                    ############################
                    # 3. merge files
                    ############################
                    st.write('Merging files ...')

                    # merge data from quickFile & standardFile
                    ############################################
                    try:
                        # find infos in txt-files
                        sst.condElements = ['Element', ' '.join(re.findall(r'(?s)Elements\s*?((?!\s*?Condition\s*?)(?!\s*?O\s*?(?:\n|\r\n?)Mode\s*?)\D*?)(?:\n|\r\n?)', quickData)).split()]
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
                        # measurement conditions
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
                        # names
                        condStdNames = [re.search(r'(?s)Standard Data.*?(?:\n|\r\n)\s*?' + str(i) + r'\s\S*\s*(.*?)\s', standardData).group(1).strip() for i in range(1,len(sst.condElements[1])+1)]
                        # detection limits (from summary.csv)
                        condStdDetLim = [(str(round(csvSummaryData[sst.condElements[1][i] + '(D.L.)'].median(),2)) + ' ± ' + str(round(csvSummaryData[sst.condElements[1][i] + '(D.L.)'].std(),2))) if (sst.condElements[1][i] + '(D.L.)' in csvSummaryData) else pd.Series('-',name=sst.condElements[1][i] + '(D.L.)') for i in range(len(sst.condElements[1]))]
                        # project names
                        condStdProjects = [re.search(r'(?s)Standard Condition.*?Project.*?\s*' + sst.condElements[1][i] + r'\s*\S{3}\s*' + condStdNames[i] + r'(.*?)\s*\S*(?:\n|\r\n)', quickData).group(1).strip() if re.search(r'(?s)Standard Condition.*?Project.*?\s*' + sst.condElements[1][i] + r'\s*\S{3}\s*' + condStdNames[i] + r'(.*?)\s*\S*(?:\n|\r\n)', quickData) != None else None for i in range(len(sst.condElements[1]))]
                        # standard data conditions
                        sst.condStd = ['Standard',
                            ['Std Name', condStdNames],
                            ['Detection Limit (μg/g)', condStdDetLim],
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
                        
                        # merge to dataframes
                        firstCol = []
                        dataCol = []
                        for i in range(1,len(sst.condInfos)):
                            firstCol.append(sst.condInfos[i][0])
                            dataCol.append(sst.condInfos[i][1])
                        sst.methodGeneralData = pd.DataFrame(data=dataCol, index=firstCol, columns=['Value'])
                        
                        firstCol = []
                        dataCol = []
                        for i in range(1,len(sst.condSamples)):
                            firstCol.append(sst.condSamples[i][0])
                            dataCol.append(sst.condSamples[i][1])
                        sst.methodSampleData = pd.DataFrame(data=dataCol, index=firstCol, columns=sst.condElements[1])
                        
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

                    # merge data from normalFile & csvSummary
                    ############################################
                    try:                           
                        new = pd.merge(csvSummaryData, df, on='Point', validate='one_to_one')
                        # delete unneeded columns
                        k = ['Norm%', 'mole%', 'K-ratio', 'K-raw', 'Net', 'BG-', 'BG+', 'L-value', 'Error%', 'D.L.', 'Unnamed'] # by keyword
                        for key in k:
                            new = new[new.columns.drop(list(new.filter(regex=key)))]
                        new = new.drop(columns=new.columns[new.columns == ' ']) # without column header
                        # set index
                        new = new.set_index('Point')
                        # rename some headers
                        new.columns = new.columns.str.replace('Mass%', 'wt%').str.replace('Cation', 'cat/24ox').str.replace('(', ' (').str.replace('Comment','Sample Name')
                        # save in session state
                        sst.csvMerged = new 
                    except:
                        st.error('An error occurred while merging your ' + csvSummaryName + '-file and ' + normalName + '-file, please check them and try again.', icon=':material/sync_problem:')
                        kadiStatus.update(label='Something went wrong, please read the corresponding error message for details.', state='error', expanded=True)
                        kadiError = True
                        st.stop()
                    
                    
                    # short measurement conditions
                    ################################
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
                

                    st.write('Merging complete!')
                    
                    ############################
                    # 4. load filter settings
                    ############################
                    if len(kadiFilter) >= 0:
                        st.write('Loading saved filter settings ...')
                        for i, filterID in enumerate(kadiFilter.keys()):
                            data = json.loads(kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + filterID + '/download'))
                            sst.kadiFilter[data['updateTime']] = data
                

                #######################
                #
                #       MAPS
                #
                #######################
                
                ###################
                #  load map files 
                ###################
                if len(mapFiles) > 0:
                    # loading progress bar
                    mapsLoaded = 0
                    sst.mapData = {}
                    progressTxt = 'Loading map data files, this may take a while ... (' + str(mapsLoaded) + '/' + str(len(mapFiles)) + ' loaded)'
                    mapProgress = st.progress(0, text=progressTxt)
                    for mapId in mapFiles.keys():
                        parts = mapFiles[mapId].split(' ')
                        if len(parts) == 5:                      
                            sst.mapData[mapFiles[mapId]] = {
                                                            'type': ('EDS' if 'Eds' in parts[2] else 'WDS'),
                                                            'set': int(parts[1]),
                                                            'no': int(parts[2].lstrip('EdsData').lstrip('data')),
                                                            'element': parts[3],
                                                            'characteristicLine': parts[4].rstrip('.csv'),
                                                            'imgData': pd.read_csv(
                                                                    io.StringIO(kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + mapId + '/download').decode('utf_8')), header=None, index_col=False, engine='python'
                                                                    ),
                                                            }              
                        
                        
                        mapsLoaded = mapsLoaded + 1
                        progressTxt = 'Loading map data files, this may take a while ... (' + str(mapsLoaded) + '/' + str(len(mapFiles)) + ' loaded)'                                    
                        mapPercent = (100/len(mapFiles)*mapsLoaded)/100
                        mapProgress.progress(mapPercent, text=progressTxt)


                #######################
                #
                #       ALL
                #
                #######################
                
                #################################################
                #    load image files (after merging to 
                #    decrease loading time if above fails)
                #################################################
                if len(imageFiles) >= 0:
                    # loading progress bar
                    imgLoaded = 0
                    progressTxt = 'Loading image data, this may take a while ... (' + str(imgLoaded) + '/' + str(len(imageFiles)) + ' loaded)'
                    imgProgress = st.progress(0, text=progressTxt)
                    for imageId in imageFiles.keys():
                        if '.tif' in imageFiles[imageId] or '.tiff' in imageFiles[imageId]:
                            sst.imageData = sst.imageData + [[imageId, tiff.imread(io.BytesIO(kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + imageId + '/download')))]]
                        elif '.jpg' in imageFiles[imageId] or '.jpeg' in imageFiles[imageId]:
                            sst.imageData = sst.imageData + [[imageId, Image.open(io.BytesIO(kadiLoadFile('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + imageId + '/download')))]]
                        
                        imgLoaded = imgLoaded + 1
                        progressTxt = 'Loading image data, this may take a while ... (' + str(imgLoaded) + '/' + str(len(imageFiles)) + ' loaded)'                                    
                        imgPercent = (100/len(imageFiles)*imgLoaded)/100
                        imgProgress.progress(imgPercent, text=progressTxt)
                    sst.imageFiles = imageFiles
                    
                ###########
                # Success
                ###########
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
def kadiUploadFilters(parentContainer):
    parentContainer.empty()
    with parentContainer.container():
        with st.status('Uploading filter settings to Kadi4Mat, please wait ...', expanded = True) as kadiUploadStatus:   
            st.write('Connecting ...')
            url = 'https://kadi4mat.iam.kit.edu/api/records/' + str(int(sst.recordID)) + '/uploads'
            if sst.kadiPAT == '':
                authPAT = st.secrets['kadiPAT']
            else:
                authPAT = sst.kadiPAT
            headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authPAT}
            metadata = {'name': 'filter_' + sst.dataViewerFilter['updateTime'] + '.txt', 'size': len(json.dumps(sst.dataViewerFilter))}
            # start upload process
            response = requests.post(url, headers=headers, json=metadata)
                        
            if response.status_code == 201:
                st.write('Starting upload progress ...')
                uploadResponse = response.json()
                uploadID = uploadResponse['id']
                uploadURL = uploadResponse['_actions']['upload_data']
                uploadData = json.dumps(sst.dataViewerFilter)
                uploadHeaders = {'Content-Type': 'application/octet-stream', 'Authorization': 'Bearer ' + authPAT}
                # send data content
                response = requests.put(uploadURL, headers=uploadHeaders, data=uploadData)
                
                if response.status_code == 200 or response.status_code == 201:
                    st.success('Filter successfully uploaded.', icon=':material/cloud_done:')
                    kadiUploadStatus.update(label='Filter successfully uploaded.', state='complete')
                else:
                    st.error('Upload failed (' + str(response.reason) + ').', icon=':material/sync_problem:')
                    kadiUploadStatus.update(label='Upload failed (' + str(response.reason) + ').', state='error')
            else:
                if response.status_code == 409:
                    st.error('Filter already uploaded!', icon=':material/cloud_done:')
                    kadiUploadStatus.update(label='Filter already uploaded!', state='error')
                else:
                    st.error('Upload failed (' + str(response.reason) + ').', icon=':material/sync_problem:')
                    kadiUploadStatus.update(label='Upload failed ( ' + str(response.reason) + ').', state='error')
    return