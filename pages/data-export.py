#######################
# imports & cofig
#######################
# imports
from utils.imports import (st, sst, requests, urllib, datetime, pd, io, re, os, io, re, os, Image, tiff, base64, imagecodecs, html, copy, alt, np, go) #, annotated_text, key
import utils.func as fn
from utils.funcKadi import (kadiGetData, kadiLoadImg, kadiUploadFilters, getMetadataValue)

import zipfile # for img download
import xlsxwriter # for xlsx download

#page config
st.set_page_config(page_title='EPMA Data Tools', page_icon='./app/static/logo.png', layout='wide', initial_sidebar_state='expanded')

# check session state
fn.checkSessionState()

# refresh oauth token if logged in
fn.refreshOauthToken()


#######################
# css
#######################
fn.loadCSS()


#########################
# extra variables
#########################
global uploadData
global uploadRecordID
global filenamePreData
filenamePreData = 'proc_'
global filenamePostData
filenamePostData = ''
global filenamePreCond
filenamePreCond = 'proc_'
global filenamePostCond
filenamePostCond = ''

#########################
# export functions
#########################
# click zip button
def compileZipImg():
    sst.createZipImg = 1
     
# initiate img to zip button
def imgZipDownloadButton():
    if sst.createZipImg == 1:
        with st.status('Loading image data and compiling zip-archive, please wait ...', expanded = True) as zipStatus:        
            
            imgLoaded = 0
            progressTxt = 'Adding images to zip-archive ... (' + str(imgLoaded) + '/' + str(len(sst.imageFiles)) + ' images processed)'
            imgProgress = st.progress(0, text=progressTxt)
            
            # create BytesIO object to store zip file in memory
            zipBytes = io.BytesIO()
            with zipfile.ZipFile(zipBytes, 'w') as zipFile:
                for imgId in sst.imageFiles:
                    # disable automatic redirection
                    response = kadiLoadImg('https://kadi4mat.iam.kit.edu/api/records/' + sst.recordID + '/files/' + imgId + '/download')
                    # extract filename from response headers
                    filename = sst.imageFiles[imgId]
                    # add image to zip file
                    zipFile.writestr(filename, response.content)
                    # update progress
                    imgLoaded = imgLoaded + 1
                    progressTxt = 'Adding images to zip-archive ... (' + str(imgLoaded) + '/' + str(len(sst.imageFiles)) + ' images processed)'                                   
                    imgPercent = (100/len(sst.imageFiles)*imgLoaded)/100
                    imgProgress.progress(imgPercent, text=progressTxt)
            zipData = zipBytes.getvalue()
            
            filename = sst.recordName + '_image-files.zip'
            st.success('Compiling complete! Download your zip-archive below.', icon=':material/folder_zip:')
            zipStatus.update(label='Compiling complete!', state='complete', expanded=False)
        
        # download button
        st.download_button('**Save ' + filename + '**', zipData,
                    file_name = filename,
                    icon=':material/folder_zip:',
                    mime = 'application/zip',
                    type = 'primary',
                   )
   

#########################
# kadi upload functions
#########################
# data filter settings
def showKadiUploadDataFilter():
    uploadPlaceholder = st.empty()
    with uploadPlaceholder.container():      
        if not sst.csvMergedFiltered.empty and 'filterColumns' in sst.dataViewerFilter and sst.dataViewerFilter['filterColumns'] != []:
            if st.button('**Upload data filter settings to Kadi4Mat**', type='primary', icon=':material/filter_arrow_right:', key='kadiUpDataFilter'):
                kadiUploadFilters(uploadPlaceholder, 'data')
        elif sst.csvMerged.empty:
            st.info('No measurement data found in this record.')
        else:
            st.info('No filters applied.  \n\n Check out **:material/filter_alt: Data Filter** under ' + fn.pageNames['viewer']['ico'] + ' **' + fn.pageNames['viewer']['name'] + '** to filter you data first.', icon=':material/filter_alt_off:')

# map display settings
def showKadiUploadMapSettings():
    uploadPlaceholder = st.empty()
    with uploadPlaceholder.container():      
        if sst.mapEditFilter != {}:
            if st.button('**Upload map display settings to Kadi4Mat**', type='primary', icon=':material/developer_board:', key='kadiUpMap'):
                kadiUploadFilters(uploadPlaceholder, 'maps')
        elif sst.mapData == {}:
            st.info('This record contains no element maps.', icon=':material/visibility_off:')
        else:
            st.info('No filters applied.  \n\n Check out **:material/map: Element Maps** under ' + fn.pageNames['viewer']['ico'] + ' **' + fn.pageNames['viewer']['name'] + '** to edit your maps first.', icon=':material/developer_board_off:')
   
#########################
# sidebar
#########################
fn.renderSidebar('menuRedirect')


#########################
# exports
#########################
st.title('Data Export', anchor=False)

if not sst.kadiLoaded:
    st.info('Please import your EPMA data in ' + fn.pageNames['import']['ico'] + ' **' + fn.pageNames['import']['name'] + '** in the sidebar menu.', icon=fn.pageNames['import']['ico'])
else:
    #########################
    # xlsx download
    #########################   
    st.subheader('Download as Excel Spreadsheet (*.xlsx)', anchor=False)
    
    st.write('Please choose the data that should be included in the downloaded file.')
    
    # toggle switches
    if not sst.kadiMetaData.empty:
        toggleMetadata = st.toggle('Include Kadi4Mat metadata in file', value=True, key='selectMetadata')
    else:
        toggleMetadata = st.toggle('Include Kadi4Mat metadata in file', 
                value=False,
                disabled=True,
                help='No metadata found on Kadi4Mat.',
                key='selectMetadata')
    
    if not sst.csvMerged.empty:
        toggleDataOriginal = st.toggle('Include merged EPMA data in file', value=True, key='selectOrig')
    else:
        toggleDataOriginal = st.toggle('Include merged EPMA data in file', 
                value=False,
                disabled=True,
                help='No EPMA measurement data found in this record.',
                key='selectOrig')
    
    if not sst.methodGeneralData.empty and sst.shortMeasCond != {}:
        toggleConditions = st.toggle('Include measurement conditions in file:', value=True, key='selectCond')
        if toggleConditions:
            left, right = st.columns((1,20))
            left.write('↳')
            with right:
                toggleConditionsShort = st.toggle('Compact Measurement Conditions', value=True, key='selectCondShort')
                toggleConditionsFull = st.toggle('Full Measurement Conditions', value=False, key='selectCondFull')
                if sst.standardsXlsx != {}:
                    toggleStandardinfo = st.toggle('Standard Information', value=True, key='selectStandardinfo')
                else:
                    toggleStandardinfo = st.toggle('Standard Information',
                        value=False,
                        disabled=True,
                        help='No standard information found in this record.',
                        key='selectStandardinfo')
                    toggleStandardinfo = False
                
    else:
        toggleConditions = st.toggle('Include measurement conditions in file:',
                value=False,
                disabled=True,
                help='No measurement conditions found in this record.',
                key='selectCond')
        toggleConditionsShort = False
        toggleConditionsFull = False
            
    if not sst.csvMergedFiltered.empty and sst.dataViewerFilter['filterColumns'] != []:
        toggleDataFiltered = st.toggle('Include filtered data in file', value=True, key='selectFilter')
    else:
        toggleDataFiltered = st.toggle('Include filtered data in file', 
                value=False, 
                disabled=True, 
                help='No filters applied. Check out ' + fn.pageNames['viewer']['ico'] + ' **' + fn.pageNames['viewer']['name'] + '** to filter you data first.', 
                key='selectFilter')
    if not sst.csvMergedMinerals.empty:
        toggleDataMinerals = st.toggle('Include mineral predictions in file', value=True, key='selectMineral')
    else:
        toggleDataMinerals = st.toggle('Include mineral predictions in file', 
                value=False, 
                disabled=True, 
                help='Please perform ' + fn.pageNames['mineral']['ico'] + ' **' + fn.pageNames['mineral']['name'] + '** to include predicted minerals and calculated mineral formulas in the downloaded file.', 
                key='selectMineral')
    
    # file generation
    uploadData = io.BytesIO()
    ## write dataframes to excel
    with pd.ExcelWriter(uploadData, engine='xlsxwriter') as writer:
        workbook=writer.book
        if toggleMetadata:
            worksheet0=workbook.add_worksheet('kadi_metadata')
            writer.sheets['kadi_metadata'] = worksheet0
            sst.kadiMetaData.to_excel(writer, sheet_name='kadi_metadata', startrow=0, startcol=0)
        
        if toggleDataOriginal:
            worksheet1=workbook.add_worksheet('merged_data')
            writer.sheets['merged_data'] = worksheet1
            sst.csvMerged.to_excel(writer, sheet_name='merged_data', startrow=0, startcol=0)
        
        if toggleDataFiltered:
            worksheet2=workbook.add_worksheet('filtered_data')
            writer.sheets['filtered_data'] = worksheet2
            sst.csvMergedFiltered.to_excel(writer, sheet_name='filtered_data', startrow=0, startcol=0)

        if toggleDataMinerals:
            worksheet3=workbook.add_worksheet('mineral_predictions')
            writer.sheets['mineral_predictions'] = worksheet3
            ## rename some keys
            keyList = sst.csvMergedMinerals.columns.tolist()
            keysRemove = ['1st Mineral formula','2nd Mineral formula']
            for key in keysRemove:
                if key in keyList:
                    keyList.remove(key)
            rename = {'1st Mineral formula_export': '1st Mineral formula', '2nd Mineral formula_export': '2nd Mineral formula'}
            sst.csvMergedMinerals[
                                    keyList
                                    ].rename(
                                                columns=rename
                                            ).to_excel(
                                                        writer,
                                                        sheet_name='mineral_predictions',
                                                        startrow=0, 
                                                        startcol=0
                                                    )
            ## references
            worksheet4=workbook.add_worksheet('references_mineral-calculation')
            writer.sheets['references_mineral-calculation'] = worksheet4
            pd.DataFrame(sorted(sst.referenceDict.items()), columns=['Author (Year)', 'DOI']).to_excel(writer, sheet_name='references_mineral-calculation', index=False)
        
        if toggleConditions:
            # compact
            if toggleConditionsShort:
                worksheet5=workbook.add_worksheet('conditions_short')
                writer.sheets['conditions_short'] = worksheet5
                worksheet5.write(0, 0, 'Summary of Measurement Conditions')
                sst.shortMeasCond[0].to_excel(writer, sheet_name='conditions_short', startrow=1, startcol=0)
                sst.shortMeasCond[1].to_excel(writer, sheet_name='conditions_short', startrow=len(sst.shortMeasCond[0])+4, startcol=0)
            # full
            if toggleConditionsFull:
                worksheet6=workbook.add_worksheet('conditions_full')
                writer.sheets['conditions_full'] = worksheet6
                worksheet6.write(0, 0, 'General Information')
                sst.methodGeneralData.to_excel(writer, sheet_name='conditions_full', startrow=1, startcol=0)
                worksheet6.write(len(sst.methodGeneralData)+3, 0, 'Measurement Conditions')
                sst.methodSampleData.to_excel(writer, sheet_name='conditions_full', startrow=len(sst.methodGeneralData)+4, startcol=0)
                worksheet6.write(len(sst.methodGeneralData)+len(sst.methodSampleData)+7, 0, 'Standard Data')
                sst.methodStdData.to_excel(writer, sheet_name='conditions_full', startrow=len(sst.methodGeneralData)+len(sst.methodSampleData)+8, startcol=0)
            # standard information
            if toggleStandardinfo:
                worksheet7=workbook.add_worksheet('standard_information')
                writer.sheets['standard_information'] = worksheet7
                startRow = 0
                for sheet in sst.standardsXlsxExport:
                    worksheet7.write(startRow, 0, sheet)
                    sst.standardsXlsxExport[sheet].to_excel(writer, sheet_name='standard_information', startrow=startRow+1, startcol=0)
                    startRow = startRow + len(sst.standardsXlsxExport[sheet].data)+3

        ## close pandas excel writer and output excel file to uploadData
        writer.close()
        
        filename = sst.recordName + '_data-export.xlsx'
        
        # download button
        st.download_button(
            label = '**Save ' + filename + '**',
            data = uploadData,
            file_name = filename,
            mime = 'application/vnd.ms-excel',
            type = 'primary',
            icon=':material/table_convert:',
                )
    
    
    #########################
    # images & element maps
    #########################   
    st.write('')
    st.subheader('Download image files (*.jpg, *.tif) as zip-archives', anchor=False)
    if len(sst.imageData) > 0:
        if sst.createZipImg == 1:
            imgZipDownloadButton()
        else:
            st.button('**Click to compile images to zip-archive**', type='primary', icon=':material/folder_zip:', key='imgDown', on_click=compileZipImg)
    else:
        st.info('This record contains no images.', icon=':material/visibility_off:')
    
    if len(sst.mapData) > 0:
        # create BytesIO object to store zip file in memory
        zipBytes = io.BytesIO()
        with zipfile.ZipFile(zipBytes, 'w') as zipFile:
            for imgId in sst.mapImages:
                # add image to zip file
                zipFile.writestr(imgId, sst.mapImages[imgId])
                
        zipDataMap = zipBytes.getvalue()
        
        filename = sst.recordName + '_map-files.zip'
        
        # download button
        st.download_button('**Save ' + filename + '**', zipDataMap,
                    file_name = filename,
                    icon=':material/folder_zip:',
                    mime = 'application/zip',
                    type = 'primary',
                   )
    else:
        st.info('This record contains no element maps.', icon=':material/visibility_off:')
    
    st.divider()
    

    #########################
    # kadi
    #########################
    st.title('Filter upload to Kadi4Mat', anchor=False)
    left, right, filler = st.columns([1,1,1])
    
    with left:
        st.subheader('Data filter settings', anchor=False)
        
        if sst.userType == 'kadi' and sst.userLoggedIn:
            showKadiUploadDataFilter()
        elif sst.userType == 'ag':
            # re-check if user is logged in or has correct pw for record
            response = kadiGetData('records/' + str(sst.recordID) + '/extras/export/json')
            pwdKadi = getMetadataValue(response.json(), 'password')
            if pwdKadi == '':
                st.info('This record is currently not accessible via password. Please contact lab head to gain access.')
            elif sst.pwdUser == pwdKadi:
                showKadiUploadDataFilter()
            else:
                st.info('You are currently not authorized to load data to this record. Log in with Kadi4Mat or import password-required IfG GUF-records first.', icon=':material/vpn_key_off:')
        else:
            st.info('You are currently not authorized to load data to this record. Log in with Kadi4Mat or import password-required IfG GUF-records first.', icon=':material/vpn_key_off:')
    
    with right:
        st.subheader('Map display settings', anchor=False)
        
        if sst.userType == 'kadi' and sst.userLoggedIn:
            showKadiUploadMapSettings()
        elif sst.userType == 'ag':
            # re-check if user is logged in or has correct pw for record
            response = kadiGetData('records/' + str(sst.recordID) + '/extras/export/json')
            pwdKadi = getMetadataValue(response.json(), 'password')
            if pwdKadi == '':
                st.info('This record is currently not accessible via password. Please contact lab head to gain access.')
            elif sst.pwdUser == pwdKadi:
                showKadiUploadMapSettings()
            else:
                st.info('You are currently not authorized to load data to this record. Log in with Kadi4Mat or import password-required IfG GUF-records first.', icon=':material/vpn_key_off:')
        else:
            st.info('You are currently not authorized to load data to this record. Log in with Kadi4Mat or import password-required IfG GUF-records first.', icon=':material/vpn_key_off:')