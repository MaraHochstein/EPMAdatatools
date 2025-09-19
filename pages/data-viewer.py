#######################
# imports & cofig
#######################
# imports
from utils.imports import (st, sst, requests, urllib, datetime, pd, io, re, os, io, re, os, Image, tiff, base64, imagecodecs, html, copy, alt, np, go)
import utils.func as fn

from pandas.api.types import (is_datetime64_any_dtype, is_numeric_dtype) # for dataframe_explorer

import matplotlib.pyplot as plt # for element maps (plotting)
import matplotlib.patches as patches
import matplotlib.cm as cm # for element maps (colors)
from matplotlib import colors # for histogram
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
# remove auto created "Footnotes" heading
st.html(
    """
<style>
#footnotes {
    display: none
}
</style>
"""
)


#########################
# display functions
#########################

# reset mapEdit if filter settings change
def resetMapEdit():
    sst.mapEdit = ''


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
        # recalculate FeO to Fe2O3
        st.subheader(':material/function: Recalculate FeO to Fe₂O₃')            
        sst.recalculateFeO = st.toggle('Recalculate FeO (wt%) to Fe₂O₃ (wt%) – this adds another column to the filtered dataset', value=False, disabled='FeO (wt%)' not in df.columns, label_visibility='visible', help='The value of FeO (wt%) will be multiplied by 1.111')
        if sst.recalculateFeO:
            df['Fe2O3 (wt%)'] = df['FeO (wt%)'] * 1.111
            df.insert(df.columns.get_loc('FeO (wt%)'), 'Fe2O3 (wt%)', df.pop('Fe2O3 (wt%)'))
        else:
            if 'Fe2O3 (wt%)' in df.columns:
                # delete Fe2O3 from table if toggle off
                df.drop(columns=['Fe2O3 (wt%)'], inplace=True)
        
        # delete Fe2O3 from filter settings if not in table
        if 'Fe2O3 (wt%)' not in df and 'Fe2O3 (wt%)' in sst.dataViewerFilter['filterSettings']:
            del sst.dataViewerFilter['filterSettings']['Fe2O3 (wt%)']
            sst.dataViewerFilter['filterColumns'].remove('Fe2O3 (wt%)')
        
        st.subheader(':material/filter_alt: Filter columns')
        # show info if duplicates have been renamed        
        if sst.csvMerged['Sample Name'].str.contains('_dupl', na=False).any():
            st.warning('Some Sample Names have been renamed to merge the raw data files. You can filter these samples by the *_dupl*-suffix in the *Sample Name* column below.', icon=':material/info:')
                
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
                    st.write('Filter values for :primary-background[' + str(column) + ']')
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
                    st.write('Filter values for :primary-background[' + str(column) + ']')
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
        # exclude element & characteristic line for COMPO
        if ('COMPO' in selectedType and val['type'] == 'COMPO') and (val['sample'] in selectedSet):
            filteredMaps[key] = val
        # WDS / EDS
        if val['element'] in selectedElements and val['characteristicLine'] in selectedTransition and val['sample'] in selectedSet and val['type'] in selectedType: 
            filteredMaps[key] = val
    return filteredMaps


# sort filtered maps by following order: sample name -> Element -> characteristic Line -> measurement type
def sortFilteredMaps(selectedMap):
    parts = selectedMap.split()
    
    # sort by own order (not for COMPO)
    sampleName = parts[1]
    elementName = parts[3] if len(parts) > 3 else '' 
    characteristicLine = parts[4] if len(parts) > 4 else ''
    measurementType = parts[2] if len(parts) > 2 else ''
    
    return (sampleName, elementName, characteristicLine, measurementType)


# colorbar preview
@st.cache_data(show_spinner=False)
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
    st.image(buf, use_container_width=True, output_format='png')
 
 
# get map ranges
def getRangeSelect(editMap):
    # calculations for range slider & colorbar
    rawValues = sst.mapData[editMap]['imgData'].values.flatten().tolist()
    # calculations for display
    dataMin = int(min(rawValues))
    dataMax = int(max(rawValues))
    dataMean = int(round(sum(rawValues)/len(rawValues),1))
    dataStd = int(round(np.std(rawValues),1))
    # range select
    if editMap in sst.mapEditFilter['filterSettings']:
        # get values from sst
        rangeSelMin = int(sst.mapEditFilter['filterSettings'][editMap]['min'])
        rangeSelMax = int(sst.mapEditFilter['filterSettings'][editMap]['max'])
    else:   
        # range select preset: mean +- 3 std dev (normal distribution) 
        rangeSelMin = int(max(dataMean - (2*dataStd), (dataMin if dataMin > 0 else 0))) # sets 0 if smaller
        
        rangeSelMax = int(min(dataMean + (2*dataStd), dataMax)) # sets to dataMax if higher
        
    return dataMin, dataMax, dataMean, dataStd, rangeSelMin, rangeSelMax


# get previous and next map name
@st.cache_data(show_spinner=False)
def getNextMap(currentMap):
    # get current index of selected map +/- 1 (mod len(names) to ensure, that last entry is followed again before first etc.)
    nextMap = list(filteredMaps.keys())[(list(filteredMaps.keys()).index(currentMap) + 1) % len(list(filteredMaps.keys()))]
    return nextMap
    
@st.cache_data(show_spinner=False)                
def getPrevMap(currentMap):
    prevMap = list(filteredMaps.keys())[(list(filteredMaps.keys()).index(currentMap) - 1) % len(list(filteredMaps.keys()))]
    return prevMap

   
# plot heatmap for selected map
@st.cache_data(show_spinner=False)
def plotElementMap(selectedMap, selectedCmap, rangeSelMin, rangeSelMax, mWidth=2.5, mHeight=1.5):
    # plot
    plt.figure(figsize=(mWidth, mHeight), dpi=600)
    heatMap = sns.heatmap(pd.DataFrame(sst.mapData[selectedMap]['imgData']), 
            annot = False, 
            cmap = selectedCmap, # selected color bar
            cbar = True,
            square = True,
            # set min & max to map values
            vmin = rangeSelMin,
            vmax = rangeSelMax,
            # turn ticks off
            xticklabels = False,
            yticklabels = False,
        )
        
    plt.gca().collections[0].colorbar.ax.tick_params(labelsize=5) # numbers on colorbar
    plt.gca().collections[0].colorbar.set_label(label= sst.mapData[selectedMap]['element'] + ' cnt', size=5, weight='bold') # label on colorbar
    
    # save plot as img-data in sst.mapImages
    imgBuffer = io.BytesIO()
    plt.savefig(imgBuffer, format='png', bbox_inches='tight')
    imgBuffer.seek(0) # move cursor back to start of buffer
    
    mapImageData = imgBuffer.getvalue() # returned to sst.mapImages[selectedMap]
    
    plt.close()
    
    return mapImageData
   
# plot histogram for selected map
@st.cache_data(show_spinner=False)
def plotMapHistogram(editMap, selectedCmap, rangeSelMin, rangeSelMax, noBins=200):            
    # get selected colormap
    cm = plt.get_cmap(selectedCmap)
    # make copy of editMap to display
    selectedMap = sst.mapData[editMap]['imgData'].values.flatten().tolist()
    selectedMapFiltered = [x for x in selectedMap if rangeSelMin <= x <= rangeSelMax]
    
    # fig
    plt.figure(figsize=(3.5, 1))
    
    # calculate histogram, not plotting yet
    n, bins = np.histogram(selectedMapFiltered, bins=noBins)
    
    # show std rectangle in background starting from mean-3*std or 0 to mean+3*std
    rectStart = max(dataMean - 2*dataStd,0)
    rectEnd = min((dataMean + 2*dataStd)-rectStart, dataMax)
    stdRect = patches.Rectangle((rectStart, 0), rectEnd, max(n)*1.05, linewidth=0, edgecolor='r', facecolor='r', alpha=0.15, zorder=0) # std
    plt.gca().add_patch(stdRect)
    
    # plot histogram
    n, bins, patchesList = plt.gca().hist(selectedMapFiltered, bins=noBins, align='mid', zorder=1)
    
    # set color for bins
    binCenters = 0.5 * (bins[:-1] + bins[1:])
    col = binCenters - min(binCenters)
    col /= max(col)
    for c, p in zip(col, patchesList):
        plt.setp(p, 'facecolor', cm(c))
    
    # remove outline 
    for s in ['top', 'bottom', 'left', 'right']:
        plt.gca().spines[s].set(linewidth=0)

    # adjust ticks & labels
    plt.xlabel(sst.mapData[editMap]['element'] + ' cnt', fontsize=5, weight='bold')
    plt.xticks(fontsize=5)
    plt.yticks([])
    
    # insert lines to indicate current ranges
    plt.axvline(x=dataMean, color='r', linestyle='--', linewidth=1) # mean
    
    # clip x axis to desired window
    plt.gca().set_xlim(rangeSelMin, rangeSelMax)
    
    # show
    st.pyplot(plt, use_container_width = False)
    plt.close()   
  

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
    tab1, tab2, tab3, tab4, tab5 = st.tabs([':material/filter_alt: Data Filter', ':material/photo_library: Images', ':material/stylus_note: Method Section', ':material/blur_on: Element Maps', ':material/ssid_chart: Qualitative Spectra'])

    with tab1:
        ################
        # Data Filter
        ################
        if not sst.csvMerged.empty:
            
            # load presets from kadi
            st.subheader(':material/rule_settings: Load filter settings from Kadi4Mat')
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
                if st.button('Load this setting', type='secondary', disabled=(sst.kadiFilter == {}), key="loadDataFilter"):
                    presetSelected = selectBox
                else:
                    presetSelected = None
            
            # get preset filter if chosen and write to current filter settings
            if presetSelected != None:
                sst.dataViewerFilter = sst.kadiFilter[presetSelected]
            
            # show data filter & table
            sst.csvMergedFiltered = dataframe_explorer(sst.csvMerged, case=False)
            st.subheader('Filtered data (' + str(len(sst.csvMergedFiltered.index)) + '/' + str(len(sst.csvMerged.index)) + ' entries filtered)' if sst.userType != 'demo' else 'Filtered data from _Quantitative Demo Dataset_ (' + str(len(sst.csvMergedFiltered.index)) + '/' + str(len(sst.csvMerged.index)) + ' entries filtered)', anchor=False)
            sst.csvMergedFiltered
            st.info('Check out **' + fn.pageNames['export']['name'] + '** if you want to download this filtered dataset or upload the filter settings to Kadi4Mat.', icon=fn.pageNames['export']['ico'])
        else:
            st.info('This record contains no measurement files.', icon=':material/visibility_off:')
        
    
    with tab2:
        ################
        # Images
        ################
        if len(sst.imageData) > 0:
            st.subheader(str(len(sst.imageData)) + ' Images saved', anchor=False)            
            #get no of img & split in groups of 4    
            imageDataSplitted = [sst.imageData[i:i+4] for i in range(0, len(sst.imageData), 4)]
            for row in imageDataSplitted:
                col1, col2, col3, col4 = st.columns(4,gap='large')
                for i, (imageId, imgData) in enumerate(row):
                    if i == 0:
                        col1.image(imgData, caption=sst.imageFiles[imageId], use_container_width=True)
                    elif i == 1:
                        col2.image(imgData, caption=sst.imageFiles[imageId], use_container_width=True)
                    elif i == 2:
                        col3.image(imgData, caption=sst.imageFiles[imageId], use_container_width=True)
                    else:
                        col4.image(imgData, caption=sst.imageFiles[imageId], use_container_width=True)
            st.info('Check out **' + fn.pageNames['export']['name'] + '** if you want to download the images (*.jpg, *.tif) as zip-archive', icon=fn.pageNames['export']['ico'])
        elif not sst.importImages:
            st.info('Images were excluded from import. Clear the import and reload the dataset with image import enabled to show images for this record.', icon=':material/sync_disabled:')
        else:
            st.info('This record contains no image data.', icon=':material/visibility_off:')

    with tab3:
        ################
        # Methods
        ################
        # different tabs for different datatypes
        tab3a, tab3b, tab3c, tab3d, tab3e = st.tabs([':material/labs: Quantitative Conditions', ':material/blur_on: Map Conditions', ':material/ssid_chart: Qualitative Spectra', ':material/database: Kadi Metadata', ':material/stylus_note: Method Writeup'])
        
        # Quantitative Conditions
        with tab3a: 
            st.subheader('Quantitative Measurement Conditions', anchor=False)
            
            if sst.shortMeasCond == {} and sst.standardsXlsx == {} and sst.methodGeneralData.empty and sst.methodSampleData.empty and sst.methodStdData.empty:
                st.info('No quantitative measurement conditions found in this record.', icon=':material/visibility_off:')
            else:
                tab3a1, tab3a2, tab3a3 = st.tabs([':material/compress: Compact Conditions', ':material/labs: Standard Details', ':material/expand: Full Conditions']) 
                
                # Compact
                with tab3a1: 
                    st.subheader('Compact Measurement Conditions', anchor=False)
                    if sst.shortMeasCond == {}:
                        st.info('No quantitative measurement conditions found in this record.', icon=':material/visibility_off:')
                    else:
                        left, right = st.columns((1,1))
                        with left:
                            st.table(sst.shortMeasCond[0])
                        st.dataframe(sst.shortMeasCond[1], hide_index=1, use_container_width=1)
                
                # Standards.xlsx
                with tab3a2:                    
                    if sst.standardsXlsx == {}:
                        st.info('No standard data found in this record.', icon=':material/visibility_off:')
                    else:
                        for sheet in sst.standardsXlsx:
                            st.subheader('Standard Details (' + str(sheet) + ')', anchor=False)
                            st.dataframe(sst.standardsXlsx[sheet], use_container_width=1)
                        
                # Full    
                with tab3a3:
                    st.subheader('Full Measurement Conditions', anchor=False)
                    if sst.methodGeneralData.empty or sst.methodSampleData.empty or sst.methodStdData.empty:
                        st.info('No quantitative measurement conditions found in this record.', icon=':material/visibility_off:')
                    else:
                        st.subheader('General Information', anchor=False)
                        st.table(sst.methodGeneralData)
                        
                        st.subheader('Measurement Conditions', anchor=False)
                        st.table(sst.methodSampleData)
                        
                        st.subheader('Standard Data', anchor=False)
                        st.table(sst.methodStdData)        
        
        # Map Conditions
        with tab3b: 
            st.subheader('Map Measurement Conditions', anchor=False)
            
            if sst.mapGeneralData == {}:
                st.info('No map measurement conditions found in this record.', icon=':material/visibility_off:')
            else:
                # create one tab for each map sample
                mapTabNames = [':material/blur_on: ' + name.lstrip('map ') for name in sst.mapGeneralData.keys()]
                mapTabs = st.tabs(mapTabNames)
                
                for mapTabName, mapTab in zip(mapTabNames, mapTabs):
                    with mapTab:
                        mapNameJson = 'map ' + mapTabName.lstrip(':material/blur_on: ')
                        
                        # General Parameters
                        if mapNameJson in sst.mapGeneralData:
                            st.subheader('General Parameters')
                            st.table(sst.mapGeneralData[mapNameJson])
                        
                        # WDS measurements
                        if mapNameJson in sst.mapWdsData:
                            st.subheader('WDS (Wavelength-Dispersive Spectrometry) Measurement Conditions')
                            st.table(sst.mapWdsData[mapNameJson])
                           
                        # EDS measurements
                        if mapNameJson in sst.mapEdsData:
                            st.subheader('EDS (Energy-Dispersive Spectrometry) Measurement Conditions')
                            st.table(sst.mapEdsData[mapNameJson])
        
        # Qualitative Spectra
        with tab3c:
            st.subheader('Qualitative Spectra Conditions', anchor=False)
            if sst.qualitativeSpectraXlsx == {} or sst.methodQualiGeneralData.empty or sst.methodQualiSpecData.empty:
                st.info('No qualitative spectra measurement conditions found in this record.', icon=':material/visibility_off:')
            else:
                st.subheader('General Information', anchor=False)
                left, right = st.columns((1,1))
                with left:
                    st.table(sst.methodQualiGeneralData)
                
                st.subheader('Spectrometer Conditions', anchor=False)
                st.table(sst.methodQualiSpecData)
        
        # Kadi Metadata    
        with tab3d:
            st.subheader('Kadi Metadata', anchor=False)
            st.table(sst.kadiMetaData)
        
        # Method Writeup
        with tab3e: 
            if sst.condInfos != {}:
                if 'Quantitative Analysis' in sst.condInfos[1][1]:
                    st.subheader('Standard Condition Writeup', anchor=False)
            
                    # find values in text
                    mesTimes = sst.condSamples[11][1]
                    mins=[]
                    maxs=[]
                    for res in mesTimes:
                        mins.append(min(res.split()))
                        maxs.append(max(res.split()))    
                    
                    st.markdown(f'''Mineral compositions were determined using a JEOL 8530F Plus Hyperprobe at the Institut für Geowissenschaften, Goethe Universität Frankfurt. The accelerating voltage was set to :primary-background[{str(sst.condInfos[5][1])} kV] with a beam current of :primary-background[{str(sst.condInfos[6][1])} nA]. The following elements were measured: :primary-background[{', '.join(sst.condElements[1])}]. The spot analyses were performed with a focused beam of :primary-background[{str(sst.shortMeasCond[0].loc["Spotsizes used (μm)"].values[0])} µm] diameter. Peak measurement times were between :primary-background[{str(min(mins))} and {str(max(maxs))} s], and backgrounds were measured with half peak measurement times. Well characterised natural and synthetic reference materials were used for calibration and the build-in :primary-background[{sst.condInfos[8][1]} correction] was applied [^1]. The standards were calibrated to <1 rel%.

---                    
### References
[^1]: Pouchou, J.-L. & Pichoir, F. (1991): https://doi.org/10.1007/978-1-4899-2617-3_4''') # unindent to prevent from being rendered as code block
                    
                    # download text
                    st.download_button('Download text as .txt-file', 'Mineral compositions were determined using a JEOL 8530F Plus Hyperprobe at the Institut für Geowissenschaften, Goethe Universität Frankfurt. The accelerating voltage was set to ' + str(sst.condInfos[5][1]) + ' kV with a beam current of ' + str(sst.condInfos[6][1]) + ' nA. The following elements were measured: ' + ', '.join(sst.condElements[1]) + '. The spot analyses were performed with a focused beam of ' + str(sst.shortMeasCond[0].loc["Spotsizes used (μm)"].values[0]) + ' µm diameter. Peak measurement times were between ' + str(min(mins)) + ' and ' + str(max(maxs)) + ' s, and backgrounds were measured with half peak measurement times. Well characterised natural and synthetic reference materials were used for calibration and the build-in ' + sst.condInfos[8][1] + ' correction was applied (RR). The standards were calibrated to <1 rel%.'
                                        , file_name='standard-condition-writeup.txt', mime='text/plain'
                                      )
            else:
                st.info('Standard Condition Writeup could not be generated for this record.', icon=':material/visibility_off:')
                
            # Flank Method
            #with tab3e2:
            #    st.write('The atomic $Fe^{3+}/Fe_{tot}$ proportions in garnets were determined with the flank method as developed and refined by Höfer et al. (1994) and Höfer and Brey (2007). Measurements were conducted with a JEOL JXA-8530F Plus electron microprobe at the Institute für Geowissenschaften, GU Frankfurt am Main. The flank method and the quantitative elemental analyses were simultaneously conducted using WDS at 15 kV and 120 nA, with a beam diameter of 1 μm. Two spectrometers with TAPL crystals for high intensities and the smallest detector slit (300 μm) were used, with 100 s counting time for $FeL_{α}$ and $FeL_{β}$. The $Fe^{3+}/Fe_{tot}$ of garnets were determined by applying the correction for self-absorption using natural and synthetic garnets with variable total $Fe$ and $Fe^{3+}/Fe_{tot}$ known from Mössbauer ›milliprobe‹ (Höfer and Brey, 2007). The remaining 3 spectrometers carried out the simultaneous elemental analyses of $Si$, $Ti$, $Al$, $Cr$, $Fe$, $Mn$, $Ni$, $Mg$, $Ca$, $Na$, $K$ and $P$. Appropriate silicates (pyrope ($Mg$, $Al$, $Si$), albite ($Na$), $CaSiO_{3}$ ($Ca$)), phosphate ($KTiOPO_{4}$ ($Ti$, $K$, $P$)), and metals or metal oxides (iron metal ($Fe$), $NiO$ ($Ni$), $MnTiO_{3}$ ($Mn$), $Cr_{2}O_{3}$ ($Cr$)) were used as standards, and a PRZ routine was used for the matrix correction. The uncertainty in $Fe^{3+}/Fe_{tot}$ analyses is about ± 0.01 (1σ), while garnets with higher $FeO$ have smaller errors than garnets with lower $FeO$.')
            #    st.divider()
            #    st.subheader('References', anchor=False)
            #    st.markdown('Höfer et al. (1994): https://doi.org/10.1127/ejm/6/3/0407')
            #    st.markdown('Höfer & Brey (2007): https://doi.org/10.2138/am.2007.2390')

        
    with tab4:
        ################
        # Element Maps
        ################
        if sst.mapData != {} and sst.importMaps:
            st.subheader('Filter Element Maps', anchor=False)            
            
            # load map presets from kadi
            #############################
            st.write('Reload previously saved map settings from Kadi4Mat:')
            left, right = st.columns((5,1))
            with left:
                selectBox = st.selectbox('Reload saved map settings from Kadi4Mat',
                                [dateStr for dateStr in sst.mapFilter], 
                                format_func = lambda x: (datetime.datetime.strptime(x, '%Y-%m-%d_%H-%M-%S').strftime('Settings from %d.%m.%Y %H:%M:%S')),
                                index = None,
                                placeholder = ('There are no map settings saved for this record. Please adjust your desired map settings below.' if (sst.mapFilter == {}) else 'Choose a preset and click the button on the right to apply.'),
                                label_visibility = 'collapsed',
                                disabled = (sst.mapFilter == {}),
                            )
            with right:
                st.write()
                if st.button('Load this setting', type='secondary', disabled=(sst.mapFilter == {}), key="loadMapSetting"):
                    presetSelected = selectBox
                else:
                    presetSelected = None
            
            # get preset filter if chosen and write to current filter settings
            if presetSelected != None:
                sst.mapEditFilter = sst.mapFilter[presetSelected]
            # preset if no map filter is loaded
            if sst.mapEditFilter == {}:
                sst.mapEditFilter = {'filterSettings': dict(), 'updateTime': ''}

            # user filter maps
            ###################   
            with st.expander('Filter Element Maps to display', icon=':material/filter_alt:', expanded=True):
                # select map set (sample)
                selectedSet = st.segmented_control('Sample:', sorted({val['sample'] for val in sst.mapData.values()}), default=sorted({val['sample'] for val in sst.mapData.values()})[0], help='Select a sample position', label_visibility='visible', selection_mode='single', on_change=resetMapEdit)
                
                # select WDS / EDS / COMPO
                selectedType = st.pills('Measurement type:', sorted({val['type'] for val in sst.mapData.values()}, reverse=True), default=sorted({val['type'] for val in sst.mapData.values()}, reverse=True)[0], help='Select one or multiple measurement types', label_visibility='visible', selection_mode='multi', on_change=resetMapEdit)
                
                # deselect elements & characteristic line if type is COMPO
                if (len(selectedType) == 1 and selectedType[0] == 'COMPO'):
                    # select element
                    selectedElements = st.pills('Measured Elements:', sorted({val['element'] for val in sst.mapData.values() if val['element'] != ''}), default=None, help='Select one or multiple elements you want to display', label_visibility='visible', selection_mode='multi', on_change=resetMapEdit)
                    
                    # select x-ray transition line
                    selectedTransition = st.pills('Measured characteristic X-ray transition lines:', sorted({val['characteristicLine'] for val in sst.mapData.values() if val['characteristicLine'] != ''}), default=None, help='Select one or multiple measured characteristic X-ray transition lines', label_visibility='visible', selection_mode='multi', on_change=resetMapEdit)
                else:
                    # select element
                    selectedElements = st.pills('Measured Elements:', sorted({val['element'] for val in sst.mapData.values() if val['element'] != ''}), default=sorted({val['element'] for val in sst.mapData.values() if val['element'] != ''}), help='Select one or multiple elements you want to display', label_visibility='visible', selection_mode='multi', on_change=resetMapEdit)
                    
                    # select x-ray transition line
                    selectedTransition = st.pills('Measured characteristic X-ray transition lines:', sorted({val['characteristicLine'] for val in sst.mapData.values() if val['characteristicLine'] != ''}), default=sorted({val['characteristicLine'] for val in sst.mapData.values() if val['characteristicLine'] != ''})[0], help='Select one or multiple measured characteristic X-ray transition lines', label_visibility='visible', selection_mode='multi', on_change=resetMapEdit)
                    
            # filter maps by selected values
            if selectedSet != None:
                filteredMaps = filterMaps(sst.mapData, selectedElements, selectedTransition, selectedSet, selectedType)
            else:
                filteredMaps = {}
                
               
            
            
            # user colorbar
            ################
            # select color
            left, mid, right = st.columns((6,2,2))
            with left:
                cmapList = ['viridis', 'flare', 'mako', 'rocket', 'crest', 'magma', 'Spectral', 'Greys']
                # get colorpreset from filter settings
                if sst.mapEditFilter != {}:
                    if 'cmap' in sst.mapEditFilter['filterSettings']:
                        cmapCopy = sst.mapEditFilter['filterSettings']['cmap'].replace('_r','') # if reversed colorbar, don't use here
                        cmapIndex = cmapList.index(cmapCopy)
                    else:
                        cmapIndex = 0
                else:
                        cmapIndex = 0
                # colormap select
                selectedCmap = st.selectbox('Chosse a color palette', (cmapList), label_visibility='visible', index=cmapIndex)
                
            with mid:
                # toggle color reverse
                fn.addLines(2)
                if 'cmap' in sst.mapEditFilter['filterSettings']:
                    # toggle true if loaded preset has reversed cbar saved
                    if st.toggle('Reverse colorbar', value=(1 if '_r' in sst.mapEditFilter['filterSettings']['cmap'] else 0)):
                        selectedCmap = selectedCmap + '_r'
                    else:
                        selectedCmap = selectedCmap
                else:
                    # if no preset loaded
                    if st.toggle('Reverse colorbar'):
                        selectedCmap = selectedCmap + '_r'
                    else:
                        selectedCmap = selectedCmap
            
            with right:
                # preview for colorbar
                displayColorbar(selectedCmap)
            
            # save cmap in sst filterSettings
            sst.mapEditFilter['filterSettings']['cmap'] = selectedCmap
            sst.mapEditFilter['updateTime'] = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            
            # user edit map settings
            #########################
            # get map
            if sst.mapEdit == '':
                if len(filteredMaps.keys()) == 0:
                    sst.mapEdit = ''
                else:
                    sst.mapEdit = list(filteredMaps.keys())[0]
            
            st.write(sst.mapEdit)
            st.write(filteredMaps.keys())
            
            # show settings expander
            with st.expander('Adjust individual maps settings', expanded=True, icon=':material/instant_mix:'):
                # if one map is selected
                if sst.mapEdit != '':
                    # preset layout (buttons before container content! -> container gets updated correctly)
                    prv, left, mid, right, nxt = st.columns((0.25,3,0.25,3,0.25))
                    ## previous map button
                    with prv:
                        fn.addLines(14)
                        if st.button('🠈'):
                            sst.mapEdit = getPrevMap(sst.mapEdit)  
                    ## histogram
                    with left:
                        histogramContainer = st.container(border=False)
                    ## big map preview
                    with right:
                        previewContainer = st.container(border=False)
                    ## next map button
                    with nxt:
                        fn.addLines(14)
                        if st.button('🠊'):
                            sst.mapEdit = getNextMap(sst.mapEdit)
                    
                    # get range values
                    dataMin, dataMax, dataMean, dataStd, rangeSelMin, rangeSelMax = getRangeSelect(sst.mapEdit)

                    # histogram
                    with histogramContainer:
                        st.subheader('Histogram settings', anchor=False)
                        st.write('Adjust the lower and upper limits of element cnt to display:')
       
                        left2, mid2, right2 = st.columns((1,1,1))
                        with left2:                        
                            lowerInput = st.number_input('Lower limit:', min_value=dataMin, max_value=dataMax, value=rangeSelMin, step=1, placeholder='lower limit', label_visibility='visible')
                        with mid2:
                            upperInput = st.number_input('Upper limit:', min_value=dataMin, max_value=dataMax, value=rangeSelMax, step=1, placeholder='upper limit', label_visibility='visible')
                        with right2:
                            binInput = st.number_input('Number of histogram bins:', min_value=40, max_value=300, value=100, step=20, placeholder='bins', label_visibility='visible')
                        # switch lower & upper if lower > upper
                        if lowerInput > upperInput:
                            lowerInputNew = upperInput
                            upperInputNew = lowerInput
                            lowerInput = lowerInputNew
                            upperInput = upperInputNew
                            
                        # save changes in histogramsettings in sst
                        if lowerInput != rangeSelMin or upperInput != rangeSelMax or binInput != 100:
                            if sst.mapEdit in sst.mapEditFilter['filterSettings']:
                                sst.mapEditFilter['filterSettings'][sst.mapEdit]['min'] = lowerInput
                                sst.mapEditFilter['filterSettings'][sst.mapEdit]['max'] = upperInput
                                sst.mapEditFilter['filterSettings'][sst.mapEdit]['bins'] = binInput
                                sst.mapEditFilter['updateTime'] = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                            else:
                                sst.mapEditFilter['filterSettings'][sst.mapEdit] = {'min': lowerInput, 'max': upperInput, 'bins': binInput}
                                sst.mapEditFilter['updateTime'] = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                        
                        # show histogram
                        tab1, tab2 = st.tabs(['selected range', 'whole data']) # show two different histogram variants
                        with tab1:
                            if sst.mapEdit in sst.mapEditFilter['filterSettings']:
                                plotMapHistogram(sst.mapEdit, selectedCmap, sst.mapEditFilter['filterSettings'][sst.mapEdit]['min'], sst.mapEditFilter['filterSettings'][sst.mapEdit]['max'], binInput)
                            else:
                                plotMapHistogram(sst.mapEdit, selectedCmap, rangeSelMin, rangeSelMax, binInput)
                        with tab2:
                            plotMapHistogram(sst.mapEdit, selectedCmap, dataMin, dataMax, binInput)
                            
                        st.write('red dashed line = data mean | red box = data mean ± 2 ∗ σ')

                    # map preview
                    with previewContainer:
                        st.subheader('Preview', anchor=False)
                        # show map preview
                        if sst.mapEdit in sst.mapEditFilter['filterSettings']:
                            sst.mapImages[sst.mapEdit.replace('.csv','.png')] = plotElementMap(sst.mapEdit, selectedCmap, sst.mapEditFilter['filterSettings'][sst.mapEdit]['min'], sst.mapEditFilter['filterSettings'][sst.mapEdit]['max'], mWidth=5, mHeight=2)
                            # show plot
                            ## map infos
                            st.markdown('**Details for this ' + str(sst.mapData[sst.mapEdit]['element']) + ('-' if sst.mapData[sst.mapEdit]['type'] != 'COMPO' else '') + 'map of ' + str(sst.mapData[sst.mapEdit]['sample']) + '**', help='X-ray line: ' + str(sst.mapData[sst.mapEdit]['characteristicLine']) + '\n\n Type: ' + str(sst.mapData[sst.mapEdit]['type']) + '\n\n Dwell time: ' + str(sst.mapGeneralData[' '.join(sst.mapEdit.split()[:2])].loc['Dwell Time (ms)', 'Value']) + ' ms\n\n Pixel size: ' + str(sst.mapGeneralData[' '.join(sst.mapEdit.split()[:2])].loc['Pixel Size (µm) (x | y)', 'Value']).replace('|', ' µm x') + ' µm')
                            ## use st.image instead of st.pyplot to avoid "MediaFileHandler: Missing file"-error
                            st.image(sst.mapImages[sst.mapEdit.replace('.csv','.png')], use_container_width=True)
                        else:
                            sst.mapImages[sst.mapEdit.replace('.csv','.png')] = plotElementMap(sst.mapEdit, selectedCmap, rangeSelMin, rangeSelMax,  mWidth=5, mHeight=2)
                            # show plot
                            ## map infos
                            st.markdown('**Details for this ' + str(sst.mapData[sst.mapEdit]['element']) + ('-' if sst.mapData[sst.mapEdit]['type'] != 'COMPO' else '') + 'map of ' + str(sst.mapData[sst.mapEdit]['sample']) + '**', help='X-ray line: ' + str(sst.mapData[sst.mapEdit]['characteristicLine']) + '\n\n Type: ' + str(sst.mapData[sst.mapEdit]['type']) + '\n\n Dwell time: ' + str(sst.mapGeneralData[' '.join(sst.mapEdit.split()[:2])].loc['Dwell Time (ms)', 'Value']) + ' ms\n\n Pixel size: ' + str(sst.mapGeneralData[' '.join(sst.mapEdit.split()[:2])].loc['Pixel Size (µm) (x | y)', 'Value']).replace('|', ' µm x') + ' µm')
                            ## use st.image instead of st.pyplot to avoid "MediaFileHandler: Missing file"-error
                            st.image(sst.mapImages[sst.mapEdit.replace('.csv','.png')], use_container_width=True)
                        
                        st.write('Min: ' + str(dataMin) + ' | Max: ' + str(dataMax) + ' | Mean: ' + str(dataMean) + ' | Std. dev.: ' + str(dataStd))
                else:
                    st.warning('No maps found for this filter settings. Please use other filter settings above.', icon=':material/remove_done:')

            st.divider()
            
            st.info('First creation of Element Maps may take some time, this is indicated by the *RUNNING...* icon in the top right corner.', icon=':material/directions_run:')
            

            # show maps
            ############
            st.subheader('Filtered maps (' + str(len(filteredMaps)) + '/' + str(len(sst.mapData)) + ' maps filtered)' if sst.userType != 'demo' else 'Filtered maps (' + str(len(filteredMaps)) + '/' + str(len(sst.mapData)) + ' maps filtered)', anchor=False)
            
            # sort maps for display
            sortedFilteredMaps = sorted(filteredMaps.keys(), key=sortFilteredMaps)
            
            # split maps in sets of 3 (for display columns)
            filteredMapNamesSplitted = [list(sortedFilteredMaps)[i:i+3] for i in range(0, len(list(sortedFilteredMaps)), 3)]
            
            for mapName in filteredMapNamesSplitted:
                
                # split in packs of 3
                col1, col2, col3 = st.columns(3,gap='large')
                for i, mapId in enumerate(mapName):
                    if mapId in sst.mapEditFilter['filterSettings']:
                        rSelMin = sst.mapEditFilter['filterSettings'][mapId]['min']
                        rSelMax = sst.mapEditFilter['filterSettings'][mapId]['max']
                    else:
                        # get range values
                        dMin, dMax, dMean, dStd, rSelMin, rSelMax = getRangeSelect(mapId)
                    if i == 0:
                        with col1:
                            sst.mapImages[mapId.replace('.csv','.png')] = plotElementMap(mapId, selectedCmap, rSelMin, rSelMax)
                            # show plot
                            ## map infos
                            st.markdown('**Details for this ' + str(sst.mapData[mapId]['element']) + ('-' if sst.mapData[mapId]['type'] != 'COMPO' else '') + 'map of ' + str(sst.mapData[mapId]['sample']) + '**', help='X-ray line: ' + str(sst.mapData[mapId]['characteristicLine']) + '\n\n Type: ' + str(sst.mapData[mapId]['type']) + '\n\n Dwell time: ' + str(sst.mapGeneralData[' '.join(mapId.split()[:2])].loc['Dwell Time (ms)', 'Value']) + ' ms\n\n Pixel size: ' + str(sst.mapGeneralData[' '.join(mapId.split()[:2])].loc['Pixel Size (µm) (x | y)', 'Value']).replace('|', ' µm x') + ' µm')
                            ## use st.image instead of st.pyplot to avoid "MediaFileHandler: Missing file"-error
                            st.image(sst.mapImages[mapId.replace('.csv','.png')], use_container_width=True) 
                            
                            if st.button('Edit this map', key='edit' + mapId):
                                # select map as edit map
                                sst.mapEdit = mapId
                                st.rerun() # reload user settings expander
                    elif i == 1:
                        with col2:
                            sst.mapImages[mapId.replace('.csv','.png')] = plotElementMap(mapId, selectedCmap, rSelMin, rSelMax)
                            # show plot
                            ## map infos
                            st.markdown('**Details for this ' + str(sst.mapData[mapId]['element']) + ('-' if sst.mapData[mapId]['type'] != 'COMPO' else '') + 'map of ' + str(sst.mapData[mapId]['sample']) + '**', help='X-ray line: ' + str(sst.mapData[mapId]['characteristicLine']) + '\n\n Type: ' + str(sst.mapData[mapId]['type']) + '\n\n Dwell time: ' + str(sst.mapGeneralData[' '.join(mapId.split()[:2])].loc['Dwell Time (ms)', 'Value']) + ' ms\n\n Pixel size: ' + str(sst.mapGeneralData[' '.join(mapId.split()[:2])].loc['Pixel Size (µm) (x | y)', 'Value']).replace('|', ' µm x') + ' µm')
                            ## use st.image instead of st.pyplot to avoid "MediaFileHandler: Missing file"-error
                            st.image(sst.mapImages[mapId.replace('.csv','.png')], use_container_width=True) 
                            
                            if st.button('Edit this map', key='edit' + mapId):
                                sst.mapEdit = mapId
                                st.rerun()
                    else:
                        with col3:
                            sst.mapImages[mapId.replace('.csv','.png')] = plotElementMap(mapId, selectedCmap, rSelMin,rSelMax)
                            # show plot
                            ## map infos
                            st.markdown('**Details for this ' + str(sst.mapData[mapId]['element']) + ('-' if sst.mapData[mapId]['type'] != 'COMPO' else '') + 'map of ' + str(sst.mapData[mapId]['sample']) + '**', help='X-ray line: ' + str(sst.mapData[mapId]['characteristicLine']) + '\n\n Type: ' + str(sst.mapData[mapId]['type']) + '\n\n Dwell time: ' + str(sst.mapGeneralData[' '.join(mapId.split()[:2])].loc['Dwell Time (ms)', 'Value']) + ' ms\n\n Pixel size: ' + str(sst.mapGeneralData[' '.join(mapId.split()[:2])].loc['Pixel Size (µm) (x | y)', 'Value']).replace('|', ' µm x') + ' µm')
                            ## use st.image instead of st.pyplot to avoid "MediaFileHandler: Missing file"-error
                            st.image(sst.mapImages[mapId.replace('.csv','.png')], use_container_width=True) 
                            
                            if st.button('Edit this map', key='edit' + mapId):
                                sst.mapEdit = mapId
                                st.rerun()
                st.divider()
            
            st.info('Check out **' + fn.pageNames['export']['name'] + '** if you want to download these map images (*.jpg, *.tif) as zip-archive or upload the map settings to Kadi4Mat.', icon=fn.pageNames['export']['ico'])

        elif not sst.importMaps:
            st.info('Element maps were excluded from import. Clear the import and reload the dataset with map import enabled to show element maps for this record.', icon=':material/sync_disabled:')
        
        else:
            st.info('This record contains no element map data.', icon=':material/visibility_off:')
            
    with tab5:
        #########################
        # Qualitative Spectra
        #########################
        if sst.qualitativeSpectraXlsx == {}:
            st.info('No qualitative spectra found in this record.', icon=':material/visibility_off:')
        else:
            for sheet in sst.qualitativeSpectraXlsx.keys():
                st.subheader(sheet, anchor=False)
                st.line_chart(
                    sst.qualitativeSpectraXlsx[sheet],
                    x = sst.qualitativeSpectraXlsx[sheet].columns[0],
                    y = sst.qualitativeSpectraXlsx[sheet].columns[1:]
                )
                st.write('')