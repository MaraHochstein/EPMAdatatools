#######################
# imports & cofig
#######################
# imports
from utils.imports import (st, sst, requests, urllib, datetime, pd, io, re, os, io, re, os, Image, tiff, annotated_text, key, base64, imagecodecs, html, copy, alt, np, go)
import utils.func as fn

from pandas.api.types import (is_datetime64_any_dtype, is_numeric_dtype) # for dataframe_explorer

import matplotlib.pyplot as plt # for element maps (plotting)
import matplotlib.cm as cm # for element maps (colors)
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
# display functions
#########################
# dataframe filter - based on module streamlit_extras.dataframe_explorer (https://github.com/arnaudmiribel/streamlit-extras/blob/main/src/streamlit_extras/dataframe_explorer/__init__.py)
def dataframe_explorer(df: pd.DataFrame, case: bool = True) -> pd.DataFrame: # if case = True: text inputs are case sensitive    
    # sync with session_state variables
    if sst.dataViewerFilter == dict():
        filters: Dict[str, Any] = dict()
        sst.dataViewerFilter['filterSettings'] = filters
        sst.dataViewerFilter['filterColumns'] = []
    else:
        filters = sst.dataViewerFilter['filterSettings']
        to_filter_columns = sst.dataViewerFilter['filterColumns']
    
    random_key_base = pd.util.hash_pandas_object(df)
    df = df.copy()
   
    modification_container = st.container()
    
    with modification_container:
        st.write('Select columns to filter (select as many as needed):')
        to_filter_columns = st.multiselect(
                'Select columns to filter (select as many as needed):',
                [col for col in df.columns if not is_datetime64_any_dtype(df[col])],
                key=f'{random_key_base}_multiselect',
                label_visibility='collapsed',
                default=sst.dataViewerFilter['filterColumns']
                )
        
        for column in to_filter_columns:
            left, right = st.columns((1, 20))
            # number
            if is_numeric_dtype(df[column]):
                left.write('↳')
                with right:
                    annotated_text('Filter values for ', (column, ':mag:', 'rgba(111, 184, 255, 0.24)'))
                    _min = float(df[column].min())
                    _max = float(df[column].max())
                    val = (filters[column][0], filters[column][1]) if column in filters else (_min, _max)
                    step = (_max - _min) / 100
                    filters[column] = st.slider(
                        f'Values for {column}',
                        _min,
                        _max,
                        val,
                        step=step,
                        key=f'{random_key_base}_{column}',
                        label_visibility='collapsed'
                    )
                    df = df[df[column].between(*filters[column])]
            # text
            else:
                left.write('↳')
                with right:
                    val = filters[column] if column in filters else ''
                    annotated_text('Filter values for ', (column, ':mag:', 'rgba(111, 184, 255, 0.24)'))
                    filters[column] = st.text_input(
                        f'Pattern in {column}',
                        value=val,
                        key=f'{random_key_base}_{column}',
                        label_visibility='collapsed'
                    )
                    if filters[column]:
                        df = df[df[column].str.contains(filters[column], case=case)]
        
        sst.dataViewerFilter['filterColumns'] = to_filter_columns
        sst.dataViewerFilter['updateTime'] = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        sst.dataViewerFilter['filterSettings'] = {key: filters[key] for key in to_filter_columns if key in filters}
    return df


# filter maps by selected values
def filterMaps(mapData, selectedElements=None, selectedTransition=None, selectedSet=None, selectedType=None):
    filteredMaps = {}
    for key, val in mapData.items():
        if (len(selectedElements) == 0 or val['element'] in selectedElements) and \
         (len(selectedTransition) == 0 or val['characteristicLine'] in selectedTransition) and \
         (len(selectedSet) == 0 or val['set'] in selectedSet) and \
         (len(selectedType) == 0 or val['type'] in selectedType): 
            filteredMaps[key] = val
    return filteredMaps


# colorbar preview
def displayColorbar(barName):
    # get colormap with barName
    colormap = plt.get_cmap(barName, 256)
    # sample 256 colors
    colors = colormap(np.linspace(0, 1, 256))
    # make colorbar plot
    fig = plt.figure(figsize=(2.5,0.125), facecolor=(0,0,0,0)) # transparent
    fig.set_frameon(False) # no margin around plot
    ax = fig.add_axes([0, 0, 1, 1], frameon=False) # no margin around plot
    ax.set_axis_off()
    # show colorbar
    ax.imshow([colors], aspect='auto')
    # save in buffer
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    # show bar
    st.caption('Color bar preview: ' + barName + '')
    st.image(buf, use_column_width='always', output_format='png')
   
   
# plot heatmap for selected map
def plotElementMap(selectedMap):
    # calculations for display
    dataMin = pd.DataFrame(sst.mapData[selectedMap]['imgData']).min().min()
    dataMax = pd.DataFrame(sst.mapData[selectedMap]['imgData']).max().max()
    # range select
    # get median
    dataMed = pd.DataFrame(sst.mapData[selectedMap]['imgData']).median().median()
    #
    if (dataMed - dataMin) < (dataMax - dataMed):
        rangeSelMin = dataMin
        rangeSelMax = dataMin + (2*dataMed)
    else:
        rangeSelMin = dataMax - (2*dataMed)
        rangeSelMax = dataMax
    # plot
    plt.figure(figsize=(3, 2))
    heatMap = sns.heatmap(pd.DataFrame(sst.mapData[selectedMap]['imgData']), 
            annot = False, 
            cmap = selectedCmap, # selected color bar
            cbar = True,
            cbar_kws={'label': sst.mapData[selectedMap]['element'] + ' cnt', 'location': 'right'},
            square = True,
            # set min & max to map values
            vmin = rangeSelMin,
            vmax = rangeSelMax,
            # turn ticks off
            xticklabels = False,
            yticklabels = False,
        )
        
    plt.gca().collections[0].colorbar.ax.tick_params(labelsize=6)
    
    # show heatmap
    st.write('**Map.: ' + str(sst.mapData[selectedMap]['set']) + ' | Element: ' + sst.mapData[selectedMap]['element'] + ' | X-ray line: ' + sst.mapData[selectedMap]['characteristicLine'] + ' | Type: ' + sst.mapData[selectedMap]['type'] + '**')
    
    st.pyplot(plt, use_container_width = False)
    plt.close()
    
    st.write('Min: ' + str(dataMin) + ' | Max: ' + str(dataMax) + ' | Median: ' + str(dataMed))
    
    
    
    
    
#########################
# sidebar
#########################
fn.renderSidebar('menuRedirect')


#########################
# data viwer
#########################
st.title('Data Viewer', anchor=False)

if not sst.kadiLoaded:
    st.info('Please import your EPMA data in **' + fn.pageNames['import']['name'] + '** in the sidebar menu.', icon=fn.pageNames['import']['ico'])
else:
    tab1, tab2, tab3, tab4 = st.tabs([':magic_wand: Data Filter', ':frame_with_picture: Images', ':notebook: Method Section', ':world_map: Element Maps'])

    with tab1:
        ################
        # Data Filter
        ################
        if not sst.csvMerged.empty:
            st.write('The table below shows the :red[merged data] from your imported raw data. Here you can filter data which should not be used for further processing.')
            # select presets
            st.write('Reload a previously saved filter setting from Kadi4Mat:')
            left, right = st.columns((5,1))
            with left:
                selectBox = st.selectbox('Reload a saved filter setting from Kadi4Mat',
                                [dateStr for dateStr in sst.kadiFilter], 
                                format_func = lambda x: (datetime.datetime.strptime(x, '%Y-%m-%d_%H-%M-%S').strftime('Settings from %d.%m.%Y %H:%M:%S') + ' – Filtered columns: ' + ', '.join(sst.kadiFilter[x]['filterColumns'])),
                                index = None,
                                placeholder = ('There are no filter settings saved for this record. Please create your desired filter settings below.' if (sst.kadiFilter == {}) else 'Choose a filter and click the button on the right to apply.'),
                                label_visibility = 'collapsed',
                                disabled = (sst.kadiFilter == {}),
                            )
            with right:
                st.write()
                if st.button('Load this setting', type='secondary', disabled=(sst.kadiFilter == {})):
                    presetSelected = selectBox
                else:
                    presetSelected = None
            
            # get preset filter if chosen and write to current filter settings
            if presetSelected != None:
                sst.dataViewerFilter = sst.kadiFilter[presetSelected]
                
            sst.csvMergedFiltered = dataframe_explorer(sst.csvMerged, case=False)
            st.subheader('Filtered data from _@' + sst.recordName + '_ (' + str(len(sst.csvMergedFiltered.index)) + '/' + str(len(sst.csvMerged.index)) + ' entries filtered)' if sst.userType != 'demo' else 'Filtered data from _Quantitative Demo Dataset_ (' + str(len(sst.csvMergedFiltered.index)) + '/' + str(len(sst.csvMerged.index)) + ' entries filtered)', anchor=False)
            sst.csvMergedFiltered
            st.info('Check out **' + fn.pageNames['export']['name'] + '** if you want to download this filtered dataset or upload the filter settings to Kadi4Mat.', icon=fn.pageNames['export']['ico'])
        else:
            st.info('This record contains no measurement files.')
        

    with tab2:
        ################
        # Images
        ################
        if len(sst.imageData) > 0:
            st.subheader(str(len(sst.imageData)) + ' Images saved in _@' + sst.recordName + '_' if sst.userType != 'demo' else str(len(sst.imageData)) + ' Images saved in _Quantitative Demo Dataset_', anchor=False)            
            #get no of img & split in groups of 4    
            imageDataSplitted = [sst.imageData[i:i+4] for i in range(0, len(sst.imageData), 4)]
            for row in imageDataSplitted:
                col1, col2, col3, col4 = st.columns(4,gap='large')
                for i, (imageId, imgData) in enumerate(row):
                    if i == 0:
                        col1.image(imgData, caption=sst.imageFiles[imageId], use_column_width='always')
                    elif i == 1:
                        col2.image(imgData, caption=sst.imageFiles[imageId], use_column_width='always')
                    elif i == 2:
                        col3.image(imgData, caption=sst.imageFiles[imageId], use_column_width='always')
                    else:
                        col4.image(imgData, caption=sst.imageFiles[imageId], use_column_width='always')
            st.info('Check out **' + fn.pageNames['export']['name'] + '** if you want to download the images (*.jpg, *.tif) as zip-archive', icon=fn.pageNames['export']['ico'])
        else:
            st.info('This record contains no image data.')

    with tab3:
        ################
        # Methods
        ################
        # different tabs for different datatypes
        if sst.shortMeasCond != {}:
            tab3a, tab3b, tab3c = st.tabs(['Metadata', 'Measurement Conditions', 'Method Writeup'])
                
            with tab3a:
                st.subheader('Kadi Metadata', anchor=False)
                st.table(sst.kadiMetaData)
            
            with tab3b:
                tab3b1, tab3b2 = st.tabs(['Compact','Full']) 
                
                with tab3b1:
                    st.subheader('Measurement Conditions for _@' + sst.recordName + '_' if sst.userType != 'demo' else 'Measurement Conditions for _Quantitative Demo Dataset_', anchor=False)
                    left, right = st.columns((1,1))
                    with left:
                        
                        st.table(sst.shortMeasCond[0])
                        
                    
                    st.dataframe(sst.shortMeasCond[1], hide_index=1, use_container_width=1)
                    
                with tab3b2:
                    st.subheader('General Information', anchor=False)
                    st.table(sst.methodGeneralData)
                    
                    st.subheader('Measurement Conditions', anchor=False)
                    st.table(sst.methodSampleData)
                    
                    st.subheader('Standard Data', anchor=False)
                    st.table(sst.methodStdData)
            
            with tab3c:
                if sst.condInfos != {}:
                    if 'Quantitative Analysis' in sst.condInfos[1][1]:
                        st.subheader('Standard Condition Writeup for _@' + sst.recordName + '_' if sst.userType != 'demo' else 'Standard Condition Writeup for _Quantitative Demo Dataset_', anchor=False)
                
                        # find values in text
                        mesTimes = sst.condSamples[11][1]
                        mins=[]
                        maxs=[]
                        for res in mesTimes:
                            mins.append(min(res.split()))
                            maxs.append(max(res.split()))    
                        
                        string = 'Mineral compositions were determined using a JEOL 8530F Plus Hyperprobe at the Institut für Geowissenschaften, Goethe Universität Frankfurt. The accelerating voltage was set to <span style="color:#FF4B62">' + str(sst.condInfos[5][1]) + ' kV</span> with a beam current of <span style="color:#FF4B62">' + str(sst.condInfos[6][1]) + ' nA</span>. '\
                                    'The following elements were measured: <span style="color:#FF4B62">' + ', '.join(sst.condElements[1]) + '</span>. The spot analyses were performed with a focused beam of <span style="color:#FF4B62">' + str(sst.shortMeasCond[0].loc['Spotsizes used (μm)'].values[0]) + ' µm</span> diameter. Peak measurement times were between <span style="color:#FF4B62">' + str(min(mins)) + '</span> and <span style="color:#FF4B62">' + str(max(maxs)) + ' s</span>, and backgrounds were measured with '\
                                    '<span style="color:#FF4B62">half</span> peak measurement times. Well characterised natural and synthetic reference materials were used for calibration and the build-in <span style="color:#FF4B62">' + sst.condInfos[8][1] + '</span> correction was applied (RR). The standards were calibrated to <1 rel%. '
                        st.markdown(string, unsafe_allow_html=True)
                        # download text
                        st.download_button('Download text as .txt-file', 'Mineral compositions were determined using a JEOL 8530F Plus Hyperprobe at the Institut für Geowissenschaften, Goethe Universität Frankfurt. The accelerating voltage was set to ' + str(sst.condInfos[5][1]) + ' kV with a beam current of ' + str(sst.condInfos[6][1]) + ' nA. '\
                                            'The following elements were measured: ' + ', '.join(sst.condElements[1]) + '. The spot analyses were performed with a focused beam of ' + str(sst.shortMeasCond[0].loc["Spotsizes used (μm)"].values[0]) + ' µm diameter. Peak measurement times were between ' + str(min(mins)) + ' and ' + str(max(maxs)) + ' s, and backgrounds were measured with '\
                                            'half peak measurement times. Well characterised natural and synthetic reference materials were used for calibration and the build-in ' + sst.condInfos[8][1] + ' correction was applied (RR). The standards were calibrated to <1 rel%. '
                                            , file_name='standard-condition-writeup.txt', mime='text/plain'
                                          )
                        st.divider()
                        st.subheader('References', anchor=False)
                        st.markdown('Pouchou, J.-L. & Pichoir, F. (1991): https://doi.org/10.1007/978-1-4899-2617-3_4')
                    
                # Flank Method
                #with tab3c2:
                #    st.write('The atomic $Fe^{3+}/Fe_{tot}$ proportions in garnets were determined with the flank method as developed and refined by Höfer et al. (1994) and Höfer and Brey (2007). Measurements were conducted with a JEOL'\
                #                'JXA-8530F Plus electron microprobe at the Institute für Geowissenschaften, GU Frankfurt am Main. The flank method and the quantitative elemental analyses were simultaneously conducted using WDS at 15 kV and 120 nA, with '\
                #                'a beam diameter of 1 μm. Two spectrometers with TAPL crystals for high intensities and the smallest detector slit (300 μm) were used, with 100 s counting time for $FeL_{α}$ and $FeL_{β}$. The $Fe^{3+}/Fe_{tot}$ of garnets were '\
                #                'determined by applying the correction for self-absorption using natural and synthetic garnets with variable total $Fe$ and $Fe^{3+}/Fe_{tot}$ known from Mössbauer ›milliprobe‹ (Höfer and Brey, 2007). The remaining 3 '\
                #                'spectrometers carried out the simultaneous elemental analyses of $Si$, $Ti$, $Al$, $Cr$, $Fe$, $Mn$, $Ni$, $Mg$, $Ca$, $Na$, $K$ and $P$. Appropriate silicates (pyrope ($Mg$, $Al$, $Si$), albite ($Na$), $CaSiO_{3}$ ($Ca$)), phosphate ($KTiOPO_{4}$ ($Ti$, $K$, $P$)), '\
                #                'and metals or metal oxides (iron metal ($Fe$), $NiO$ ($Ni$), $MnTiO_{3}$ ($Mn$), $Cr_{2}O_{3}$ ($Cr$)) were used as standards, and a PRZ routine was used for the matrix correction. The uncertainty in $Fe^{3+}/Fe_{tot}$ analyses is about ± '\
                #                '0.01 (1σ), while garnets with higher $FeO$ have smaller errors than garnets with lower $FeO$.')
                #    st.divider()
                #    st.subheader('References', anchor=False)
                #    st.markdown('Höfer et al. (1994): https://doi.org/10.1127/ejm/6/3/0407')
                #    st.markdown('Höfer & Brey (2007): https://doi.org/10.2138/am.2007.2390')
        
        else:
            st.subheader('Kadi Metadata', anchor=False)
            st.table(sst.kadiMetaData)
            
    with tab4:
        ################
        # Element Maps
        ################
        if sst.mapData != {}:
            st.subheader('Filter Element Maps', anchor=False)
            # select element
            selectedElements = st.multiselect('Measured Elements:',({val['element'] for val in sst.mapData.values()}), default=({val['element'] for val in sst.mapData.values()}), placeholder='Select elements you want to display', label_visibility='visible')
            # select x-ray transition line
            selectedTransition = st.multiselect('Measured characteristic X-ray transition lines:', ({val['characteristicLine'] for val in sst.mapData.values()}), default=({val['characteristicLine'] for val in sst.mapData.values()}), placeholder='Select the measured characteristic X-ray transition line', label_visibility='visible')
            # select map set (position)
            selectedSet = st.multiselect('Map set (same set ⇨ same position):', ({val['set'] for val in sst.mapData.values()}), default=min({val['set'] for val in sst.mapData.values()}), placeholder='Select a map set (same set ⇨ same position)', label_visibility='visible')
            # select WDS / EDS
            selectedType = st.multiselect('Measurement type:',({val['type'] for val in sst.mapData.values()}), default=({val['type'] for val in sst.mapData.values()}), placeholder='Select the measurement type', label_visibility='visible')
            # select color
            left, right = st.columns((8,2))
            with left:
                selectedCmap = st.selectbox('Chosse a color palette', ('viridis', 'flare', 'mako', 'rocket', 'crest', 'magma', 'Spectral'), label_visibility='visible')
            with right:
                # preview for colorbar
                displayColorbar(selectedCmap)

            st.subheader('Element Maps for selected settings', anchor=False)
            
            # filter maps by selected values
            filteredMaps = filterMaps(sst.mapData, selectedElements, selectedTransition, selectedSet, selectedType)


            # split maps in sets of 3 (for display columns)
            filteredMapNamesSplitted = [list(filteredMaps.keys())[i:i+3] for i in range(0, len(list(filteredMaps.keys())), 3)]
            
            for mapName in filteredMapNamesSplitted:
                col1, col2, col3 = st.columns(3,gap='large')
                for i, mapId in enumerate(mapName):
                    if i == 0:
                        with col1:
                            plotElementMap(mapId)
                            
                                
                    elif i == 1:
                        with col2:
                            plotElementMap(mapId)
                            
                                
                    else:
                        with col3:
                            plotElementMap(mapId)
                                                           
                st.divider()
            
            st.info('Check out **' + fn.pageNames['export']['name'] + '** if you want to download these map images (*.jpg, *.tif) as zip-archive or upload the map settings to Kadi4Mat.', icon=fn.pageNames['export']['ico'])
        else:
            st.info('This record contains no element map data.')
        
     
        