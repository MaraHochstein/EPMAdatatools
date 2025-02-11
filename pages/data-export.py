#######################
# imports & cofig
#######################
# imports
from utils.imports import (st, sst, requests, urllib, datetime, pd, io, re, os, io, re, os, Image, tiff, base64, imagecodecs, html, copy, alt, np, go)
import utils.func as fn
from utils.funcKadi import (kadiGetData, kadiLoadImg, kadiUploadFilters, getMetadataValue)

import zipfile # for img download
import xlsxwriter # for xlsx download

import matplotlib.pyplot as plt # for element maps (plotting)
import seaborn as sns # for element maps (heatmap)

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
# click zip img button
def compileZipImg():
    sst.createZipImg = 1
    
# click zip map csv button
def compileZipMap():
    sst.createZipMap = 1

# click zip map png button
def compileZipMapPng():
    sst.createZipMapPng = 1
     
# initiate img to zip button
def imgZipDownloadButton():
    if sst.createZipImg == 1:
        if sst.zipBytesImg == 0:
            with st.status(':material/sync: Loading image data and compiling zip-archive, please wait ...', expanded = True) as zipStatus:        
                
                imgLoaded = 0
                progressTxt = ':material/create_new_folder: Adding images to zip-archive ... (' + str(imgLoaded) + '/' + str(len(sst.imageFiles)) + ' images processed)'
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
                        progressTxt = ':material/create_new_folder: Adding images to zip-archive ... (' + str(imgLoaded) + '/' + str(len(sst.imageFiles)) + ' images processed)'                                   
                        imgPercent = (100/len(sst.imageFiles)*imgLoaded)/100
                        imgProgress.progress(imgPercent, text=progressTxt)
                zipBytes.seek(0)
                sst.zipBytesImg = zipBytes
                
                st.success('Compiling complete! Download your zip-archive below.', icon=':material/folder_zip:')
                zipStatus.update(label='Compiling complete!', state='complete', expanded=True)
        
        filename = sst.recordName + '_image-files.zip'
        
        # download button
        st.download_button('**Save ' + filename + '**', sst.zipBytesImg,
                    file_name = filename,
                    icon=':material/folder_zip:',
                    mime = 'application/zip',
                    type = 'primary',
                    )
   
# initiate maps to zip button
def mapZipDownloadButton():
    if sst.createZipMap == 1:
        if sst.zipBytesMap == 0:
            with st.status(':material/sync: Loading map data and compiling zip-archive, please wait ...', expanded = True) as zipStatus:
                
                mapLoaded = 0
                progressTxt = ':material/create_new_folder: Adding maps to zip-archive ... (' + str(mapLoaded) + '/' + str(len(sst.mapData)) + ' maps processed)'
                mapProgress = st.progress(0, text=progressTxt)
                
                # create BytesIO object to store zip file in memory
                zipBytes = io.BytesIO()
                # add csv's to zip file
                with zipfile.ZipFile(zipBytes, 'w') as zipFile:
                    for filename, fileData in sst.mapData.items():
                        # replace filename
                        newFilename = filename.replace(' ', '-')
                        # convert data to csv
                        csvData = fileData['imgData'].to_csv(index=False)
                        zipFile.writestr(newFilename, csvData)
                        # update progress
                        mapLoaded = mapLoaded + 1
                        progressTxt = ':material/create_new_folder: Adding maps to zip-archive ... (' + str(mapLoaded) + '/' + str(len(sst.mapData)) + ' maps processed)'
                        mapPercent = (100/len(sst.mapData)*mapLoaded)/100
                        mapProgress.progress(mapPercent, text=progressTxt)
                        
                zipBytes.seek(0)
                sst.zipBytesMap = zipBytes
                
                st.success('Compiling complete! Download your zip-archive below.', icon=':material/folder_zip:')
                zipStatus.update(label='Compiling complete!', state='complete', expanded=True)
        
        filename = sst.recordName + '_map-csv.zip'
        
        # download button
        st.download_button('**Save ' + filename + '**', sst.zipBytesMap,
                    file_name = filename,
                    icon = ':material/folder_zip:',
                    mime = 'application/zip',
                    type = 'primary',
                    )

# initiate map pngs to zip button
def mapPngZipDownloadButton():
    if sst.createZipMapPng == 1:
        if sst.zipBytesMapPng == 0:
            with st.status(':material/box_edit: Creating map plots and compiling zip-archive, please wait ...', expanded = True) as zipStatus:
                
                # create missing map plots
                ## get all maps that are not yet converted to png
                missingMapPng = set(sst.mapData.keys()) - set([key.replace('.png', '.csv') for key in sst.mapImages.keys()])
                
                ## progress
                mapProcessed = 0
                progressTxt = ':material/edit_square: Creating missing map plots ... (' + str(mapProcessed) + '/' + str(len(missingMapPng)) + ' maps processed)'
                mapPngProgress = st.progress(0, text=progressTxt)
                
                ## create missing map plots
                for key in missingMapPng:
                    sst.mapImages[key.replace('.csv','.png')] = plotElementMap(key)
                    
                    ## update progress
                    mapProcessed = mapProcessed + 1
                    progressTxt = ':material/edit_square: Creating missing map plots ... (' + str(mapProcessed) + '/' + str(len(missingMapPng)) + ' maps processed)'
                    mapPngPercent = (100/len(missingMapPng)*mapProcessed)/100
                    mapPngProgress.progress(mapPngPercent, text=progressTxt)
                
                
                # add maps to zip
                ## progress
                mapLoaded = 0
                progressTxt = ':material/create_new_folder: Adding maps to zip-archive ... (' + str(mapLoaded) + '/' + str(len(sst.mapImages)) + ' maps processed)'
                mapProgress = st.progress(0, text=progressTxt)
                
                ## create BytesIO object to store zip file in memory
                zipBytes = io.BytesIO()
                with zipfile.ZipFile(zipBytes, 'w') as zipFile:
                    for imgId in sst.mapImages:
                        # add image to zip file
                        zipFile.writestr(imgId, sst.mapImages[imgId])
                        # update progress
                        mapLoaded = mapLoaded + 1
                        progressTxt = ':material/create_new_folder: Adding maps to zip-archive ... (' + str(mapLoaded) + '/' + str(len(sst.mapImages)) + ' maps processed)'
                        mapPercent = (100/len(sst.mapData)*mapLoaded)/100
                        mapProgress.progress(mapPercent, text=progressTxt)

                zipBytes.seek(0)
                sst.zipBytesMapPng = zipBytes
                
                st.success('Compiling complete! Download your zip-archive below.', icon=':material/folder_zip:')
                zipStatus.update(label='Compiling complete!', state='complete', expanded=True)
                    
        filename = sst.recordName + '_map-images.zip'
        
        # download button
        st.download_button('**Save ' + filename + '**', sst.zipBytesMapPng,
                    file_name = filename,
                    icon=':material/folder_zip:',
                    mime = 'application/zip',
                    type = 'primary',
                    )
                

# create missing element map .pngs
@st.cache_data(show_spinner=False)
def plotElementMap(selectedMap): #, mWidth=2.5, mHeight=1.5
     
    # calculations for min & max mapping values
    rawValues = sst.mapData[selectedMap]['imgData'].values.flatten().tolist()
    dataMin = int(min(rawValues))
    dataMax = int(max(rawValues))
    dataMean = int(round(sum(rawValues)/len(rawValues),1))
    dataStd = int(round(np.std(rawValues),1))

    # range select preset: mean +- 3 std dev (normal distribution)
    rangeSelMin = int(max(dataMean - (2*dataStd), (dataMin if dataMin > 0 else 0))) # sets 0 if smaller
    rangeSelMax = int(min(dataMean + (2*dataStd), dataMax)) # sets to dataMax if higher
    
    # plot
    plt.figure(figsize=(5, 2), dpi=600)
    heatMap = sns.heatmap(pd.DataFrame(sst.mapData[selectedMap]['imgData']), 
            annot = False, 
            cmap = 'viridis', # standard color bar for unedited maps
            cbar = True,
            square = True,
            # set min & max to map values
            vmin = rangeSelMin,
            vmax = rangeSelMax,
            # turn ticks off
            xticklabels = False,
            yticklabels = False,
        )
    # ensure plot elements are fully processed
    plt.draw()
    
    plt.gca().collections[0].colorbar.ax.tick_params(labelsize=5) # numbers on colorbar
    plt.gca().collections[0].colorbar.set_label(label= sst.mapData[selectedMap]['element'] + ' cnt', size=5, weight='bold') # label on colorbar
    
    # save plot as img-data in sst.mapImages
    imgBuffer = io.BytesIO()
    plt.savefig(imgBuffer, format='png', bbox_inches='tight')
    imgBuffer.seek(0) # move cursor back to start of buffer
    
    mapImageData = imgBuffer.getvalue() # returned to sst.mapImages[selectedMap]
    
    plt.close()
    
    return mapImageData


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
            if not sst.importMaps:
                st.info('Element maps were excluded from import. Clear the import and reload the dataset with map import enabled to upload element map display settings for this record.', icon=':material/sync_disabled:')
            else:
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
    st.subheader(':material/table_view: Download as Excel Spreadsheet (*.xlsx)', anchor=False)
    
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
    
    
    ###############
    # images 
    ###############   
    st.write('')
    st.subheader(':material/photo_library: Download images (\*.jpg, \*.tif) as zip-archive', anchor=False)
    # images
    if len(sst.imageData) > 0:
        if sst.createZipImg == 1:
            imgZipDownloadButton()
        else:
            st.button('**Click to compile images to zip-archive**', type='primary', icon=':material/folder_zip:', key='imgDown', on_click=compileZipImg)
    else:
        if not sst.importImages:
            st.info('Images were excluded from import. Clear the import and reload the dataset with image import enabled to download image files for this record.', icon=':material/sync_disabled:')
        else:
            st.info('This record contains no images.', icon=':material/visibility_off:')
    
    
    ###############################
    # rendered element maps pngs
    ###############################
    st.write('')
    st.subheader(':material/blur_on: Download rendered element maps (\*.png) as zip-archive', anchor=False)
    # element maps
    if len(sst.mapData) > 0:
        if sst.createZipMapPng == 1:
            mapPngZipDownloadButton()
        else:
            st.info('Map images will be downloaded as *.png-files. Element maps that have not been rendered will be exported with standard display settings. You can adjust these settings in the menu under ' + fn.pageNames['viewer']['ico'] + ' **' + fn.pageNames['viewer']['name'] + '** :material/arrow_forward: **:material/blur_on: Element Maps**. Rendering missing element maps may take some time.', icon=':material/warning:')
            st.button('**Click to compile rendered maps to zip-archive**', type='primary', icon=':material/folder_zip:', key='mapPngDown', on_click=compileZipMapPng)
    else:
        if not sst.importMaps:
            st.info('Element maps were excluded from import. Clear the import and reload the dataset with map import enabled to download element maps for this record.', icon=':material/sync_disabled:')
        else:
            st.info('This record contains no element maps.', icon=':material/visibility_off:')
    
    
    #########################
    # element maps csv
    #########################
    st.write('')
    st.subheader(':material/blur_on: Download map files (\*.csv) as zip-archive', anchor=False)
    if len(sst.mapData) > 0:
        if sst.createZipMap == 1:
            mapZipDownloadButton()
        else:
            st.button('**Click to compile map data to zip-archive**', type='primary', icon=':material/folder_zip:', key='mapDown', on_click=compileZipMap)            
    else:
        if not sst.importMaps:
            st.info('Element maps were excluded from import. Clear the import and reload the dataset with map import enabled to download element maps for this record.', icon=':material/sync_disabled:')
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