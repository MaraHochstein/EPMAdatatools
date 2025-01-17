##########################################################################################################################
# general calculation info
##########################################################################################################################
#
# STEP 1: calculate formula weights of oxides
#
#
# STEP 2: calculate molar fraction of oxides (mole units)
#
#   mole units = measured wt% / formula weight of oxide
# 
#
# STEP 3: calculate number of oxygen per oxide (oxygen units)
#
#   oxygen units = mole units * number of oxygen in oxide formula
#
#
# STEP 4: calculate number of oxygen standardized to number of of oxygens in general formula (normalized oxygen units)
#
#                               oxygen units[oxide]
#   normalized oxygen units = ---------------------- * number of oxygens in selected mineral formula
#                               oxygen units[total]
#
#
# STEP 5: calculate number of atoms for general formula (atom units)
#
#                                           number of cations in oxide
#   atom units = normalized oxygen units * ----------------------------
#                                            number of oxygen in oxide
#
#
# STEP 6: recalculate mineral formula for every mineral and sample point
#
##########################################################################################################################

#######################
# imports & cofig
#######################
# imports
from utils.imports import (st, sst, requests, urllib, datetime, pd, io, re, os, io, re, os, Image, tiff, base64, imagecodecs, html, copy, alt, np, go) #, annotated_text, key
import utils.func as fn

# page config
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
global standardAtomicWeights
standardAtomicWeights = {
    'Al': 26.982,
    'Ar': 39.948,
    'As': 74.922,
    'Bi': 208.98,
    'Br': 79.904,
    'Ca': 40.078,
    'Cr': 51.996,
    'Fe': 55.845,
    'K': 39.098,
    'Mg': 24.305,
    'Mn': 54.938,
    'Na': 22.99,
    'Ni': 58.693,
    'O': 15.999,
    'P': 30.974,
    'Si': 28.085,
    'Ti': 47.867,
    'Y': 88.906
}

# mineral formulas, site assignments and priorities are adapted from
#   MinPlot 1.1
#   https://github.com/MinPlot/MinPlot_Program
# for further references see 
#   Walters (2022) "MinPlot: A mineral formula recalculation and plotting program for electron probe microanalysis"
#   https://doi.org/10.2478/mipo-2022-0005
# all calculations are made with total Fe = Fe 2+ estimation
global standardMineralFormulas
standardMineralFormulas = {
    'Olivine': {
                'formulaElements': [{ # M site
                                        'elements': {
                                                    'Ti': {'prioEl': 1, 'cntEl': 0},
                                                    'Al': {'prioEl': 2, 'cntEl': 0}, # vi Al
                                                    # 'Fe': {'prioEl': 1, 'cntEl': 0}, # Fe 3+
                                                    'Cr': {'prioEl': 1, 'cntEl': 0},
                                                    'Ni': {'prioEl': 1, 'cntEl': 0},
                                                    'Fe': {'prioEl': 1, 'cntEl': 0}, # Fe 2+
                                                    'Mn': {'prioEl': 1, 'cntEl': 0},
                                                    'Mg': {'prioEl': 1, 'cntEl': 0},
                                                    'Ca': {'prioEl': 1, 'cntEl': 0},
                                                    },
                                        'prioSite': 2,
                                        'cntSite': 2
                                    },{ # T: tetrahedral site 4+
                                        'elements': {
                                                    'Si': {'prioEl': 1, 'cntEl': 0},
                                                    'Al': {'prioEl': 1, 'cntEl': 0}, # iv Al
                                                    },
                                        'prioSite': 1,
                                        'cntSite': 1
                                    }],
                'oxygen': 4,
                'references': {
                                
                            }
                },
    'Quartz': { 
                'formulaElements': [{ # T: tetrahedral site 4+
                                        'elements': {
                                                    'Si': {'prioEl': 1, 'cntEl': 0},
                                                    'Al': {'prioEl': 1, 'cntEl': 0},
                                                    'Ti': {'prioEl': 1, 'cntEl': 0},
                                                    'Fe': {'prioEl': 1, 'cntEl': 0},
                                                    },
                                        'prioSite': 1,
                                        'cntSite': 1
                                    }],
                'oxygen': 4,
                'references': {
                                
                            }                               
                },
    'Pyroxene': { # ideal site occupancy modified from Deer et al. (2013) after Morimoto (1988)
                'formulaElements': [{ # M2: distorted octahedral site 2+
                                        'elements': {
                                                    'Mg': {'prioEl': 2, 'cntEl': 0},
                                                    'Fe': {'prioEl': 2, 'cntEl': 0}, # Fe 2+
                                                    'Mn': {'prioEl': 2, 'cntEl': 0},
                                                    # 'Li': {'prioEl': 1, 'cntEl': 0},
                                                    'Ca': {'prioEl': 1, 'cntEl': 0},
                                                    'Na': {'prioEl': 1, 'cntEl': 0},
                                                    'K': {'prioEl': 1, 'cntEl': 0}, # see MinPlot1.1
                                                    },
                                        'prioSite': 3,
                                        'cntSite': 1
                                    },{ # M1: octahedral site 2+
                                        'elements': {
                                                    'Al': {'prioEl': 2, 'cntEl': 0}, # vi Al
                                                    # 'Fe': {'prioEl': 1, 'cntEl': 0}, # Fe 3+
                                                    # 'Ti': {'prioEl': 1, 'cntEl': 0}, # Ti 4+
                                                    'Cr': {'prioEl': 1, 'cntEl': 0},
                                                    # 'V': {'prioEl': 1, 'cntEl': 0},
                                                    'Ti': {'prioEl': 1, 'cntEl': 0}, # Ti 3+
                                                    # 'Zr': {'prioEl': 1, 'cntEl': 0},
                                                    # 'Sc': {'prioEl': 1, 'cntEl': 0},
                                                    # 'Zn': {'prioEl': 1, 'cntEl': 0},
                                                    'Mg': {'prioEl': 1, 'cntEl': 0},
                                                    'Fe': {'prioEl': 1, 'cntEl': 0}, # Fe 2+
                                                    'Mn': {'prioEl': 1, 'cntEl': 0},
                                                    },
                                        'prioSite': 2,
                                        'cntSite': 1
                                    },{ # T: tetrahedral site 4+
                                        'elements': {
                                                    'Si': {'prioEl': 1, 'cntEl': 0},
                                                    'Al': {'prioEl': 1, 'cntEl': 0}, # iv Al
                                                    # 'Fe': {'prioEl': 1, 'cntEl': 0}, # Fe 3+
                                                    },
                                        'prioSite': 1,
                                        'cntSite': 2
                                    }],
                'oxygen': 6,
                'references': {
                               'Deer et al. (2013)': 'https://doi.org/10.1180/DHZ',
                               'Morimoto (1988)': 'https://doi.org/10.1007/BF01226262',
                            }                             
                },
    'Garnet': {
                'formulaElements': [{ # X: dodecahedral site 2+
                                        'elements': {
                                                    'Y': {'prioEl': 1, 'cntEl': 0},
                                                    'Mg': {'prioEl': 2, 'cntEl': 0},
                                                    'Fe': {'prioEl': 2, 'cntEl': 0},
                                                    'Mn': {'prioEl': 1, 'cntEl': 0},
                                                    'Ca': {'prioEl': 1, 'cntEl': 0},
                                                    'Na': {'prioEl': 1, 'cntEl': 0},
                                                    },
                                        'prioSite': 3,
                                        'cntSite': 3
                                    },{ # Y: octahedral site 3+
                                        'elements': {
                                                    'Si': {'prioEl': 2, 'cntEl': 0},
                                                    'Al': {'prioEl': 2, 'cntEl': 0},
                                                    'Ti': {'prioEl': 1, 'cntEl': 0},
                                                    'Cr': {'prioEl': 1, 'cntEl': 0},
                                                    'Mg': {'prioEl': 1, 'cntEl': 0},
                                                    'Fe': {'prioEl': 1, 'cntEl': 0},
                                                    'Mn': {'prioEl': 1, 'cntEl': 0},
                                                    },
                                        'prioSite': 2,
                                        'cntSite': 2
                                    },{ # T: tetrahedral site 4+
                                        'elements': {
                                                    'Si': {'prioEl': 1, 'cntEl': 0},
                                                    'Al': {'prioEl': 1, 'cntEl': 0},
                                                    },
                                        'prioSite': 1,
                                        'cntSite': 3
                                    }],
                'oxygen': 12,
                'references': {
                                
                            }                          
                },
}


#########################
# calculation
# & display functions
#########################
## other

# make numbers subscript
def toSubscript(text):
    subscriptMapping = {
        '0': '₀',
        '1': '₁',
        '2': '₂',
        '3': '₃',
        '4': '₄',
        '5': '₅',
        '6': '₆',
        '7': '₇',
        '8': '₈',
        '9': '₉',
        ',': '',
        '.': ' ̗ '
    }
    subscriptText = ''
    for char in text:
        subscriptText += subscriptMapping.get(char, char)
    return subscriptText

# save references for mineral formula calculation in dict      
@st.cache_data(show_spinner=False)
def saveReferences(selectedMinerals):
    sst.referenceDict = {'Walters (2022)': 'https://doi.org/10.2478/mipo-2022-0005'}
    for mineral in selectedMinerals:
        for reference in standardMineralFormulas[mineral]['references']:
            sst.referenceDict[reference] = standardMineralFormulas[mineral]['references'][reference]

## calculation

# calculates atomic weight of given molecular formula (without subscripts, e.g. 'Al2O3'); use atomic weights from standardAtomicWeights
@st.cache_data(show_spinner=False)
def calcformulaWeight(formula):
    formulaWeight = 0.0
    elementCount = {}
    
    # Count the elements in the formula
    i = 0
    while i < len(formula):
        if formula[i].isupper():
            element = formula[i]
            i += 1
            while i < len(formula) and formula[i].islower():
                element += formula[i]
                i += 1
            count = ''
            while i < len(formula) and formula[i].isdigit():
                count += formula[i]
                i += 1
            if count == '':
                count = '1'
            elementCount[element] = int(count)
        else:
            i += 1
    
    # Calculate the formula weight
    for element, count in elementCount.items():
        formulaWeight += standardAtomicWeights[element] * count
    
    return formulaWeight

# splits oxide formula to extract the elements and their counts
# save as dictionary with: element name, element count, oxygen count, atomic weight of formula
@st.cache_data(show_spinner=False)
def splitOxides(oxideList):
    oxideDict = {}
    # loop through all oxides given
    for oxide in oxideList:
        # extract elements and their counts (e.g. for SiO2: oxideSplit = 'Si','','O','2')
        oxideSplit = re.findall(r'([A-Z][a-z]*)(\d*)', oxide)
        # replace '' with '1' (e.g. for SiO2: oxideSplit = 'Si','','O','2' --> 'Si', '1', 'O', '2')
        oxideSplit = [(x if x != '' else '1', y if y != '' else '1') for x, y in oxideSplit]
        # extract element name: first entry in oxideSplit (e.g. for SiO2: 'Si')
        element = oxideSplit[0][0]
        # extract element count: second entry in oxideSplit; set to 1 if none (e.g. for Ar: oxideSplit = 'Ar' --> 'Ar' --> 1 * Ar)
        elementCount = int(oxideSplit[0][1]) if oxideSplit[0][1] else 1
        # if no oxygen is found, set to 0 (e.g. for Ar --> oxideSplit = 'Ar' --> 0 * oxygen)
        oxygenCount = int(oxideSplit[1][1]) if len(oxideSplit) > 1 and oxideSplit[1][1] else 0
        # check if element is in reference table
        if element in standardAtomicWeights:
            oxideDict[oxide] = {'element': element, 'elementCount': int(elementCount), 'oxygenCount': int(oxygenCount), 'formulaWeight': calcformulaWeight(oxide)}
    
    # add 'Total' row
    oxideDict['Total'] = {}
    
    return oxideDict
    
# formula recalculation for chosen minerals for every sample point
@st.cache_data(show_spinner=False)
def calcOxides(oxideList, selectedMinerals, selectedData):
    
    # STEPS 1 - 5:
    #
    #   save calculations in oxideCalc = {SampleName1: pdDataFrame1, SampleName2: pdDataFrame2 ...}
    #
    #   where every pdDataFrame is:
    #
    #                                       |                   |   Formula weight  |   Mole units |                   |   Normalized oxygen units  |   Atom units        
    #                       Oxide           |   Measured wt%    |      (g/mol)      |   (%/(g/mol)  |   Oxygen units   |      for mineral x         |      for mineral x                                 
    #                       -> from data    |   -> from data    |   -> Step 1       |   -> Step 2   |   -> Step 3      |   --> Step 4               |   --> Step 5         
    #                   ------------------------------------------------------------------------------------------------------------------------------------------------------
    #  pdDataFrame =            SiO2        |                   |                   |               |                  |                            |                  
    #                           TiO2        |                   |                   |               |                  |                            |                
    #                           ...
    #
    
    with st.spinner('Mineral formula recalculation, please wait...'):
        # make a copy of standardMineralFormulas only containing selected minerals
        usedMineralFormulas = {key: standardMineralFormulas[key] for key in selectedMinerals}
        # set up needed columns
        calcOxidesColumns = ['Oxide', 'Element', 'Measured (wt%)', 'Formula weight (g/mol)', 'Mole units (%/(g/mol))', 'Oxygen units']
        # get indices of original data
        oxidePreCalcIndex = selectedData.index.tolist()
        # set up list of empty pdDataFrames with indices of original data
        oxideCalc = {str(i) + '-' + selectedData['Sample Name'][i]: pd.DataFrame(columns = calcOxidesColumns) for i in oxidePreCalcIndex}
        # for output
        filledFormulas = {str(i) + '-' + selectedData['Sample Name'][i]: dict() for i in oxidePreCalcIndex}
        
        # loop through all samples
        for index, row in selectedData.iterrows():        
            # loop through all oxides in list
            for oxide in oxideList:
                #################################################
                # calculate pdDataFrame for sample (step 1-3)
                #################################################
                
                oxideCalc[str(index) + '-' + row['Sample Name']] = pd.concat(
                                                    [oxideCalc[str(index) + '-' + row['Sample Name']],
                                                        pd.DataFrame(
                                                            [[  # oxide name
                                                                oxide,
                                                                # element name
                                                                oxideList[oxide]['element'] if oxide != 'Total' else '',
                                                                # measured wt%
                                                                row[oxide+' (wt%)'],
                                                                # atomic weight
                                                                oxideList[oxide]['formulaWeight'] if oxide != 'Total' else '',
                                                                # mole units (step 2)
                                                                row[oxide+' (wt%)'] / oxideList[oxide]['formulaWeight'] if oxide != 'Total' else '',
                                                                # oxygen units (step 3); for total: sum
                                                                row[oxide+' (wt%)'] / oxideList[oxide]['formulaWeight'] * oxideList[oxide]['oxygenCount'] if oxide != 'Total' else oxideCalc[str(index) + '-' + row['Sample Name']]['Oxygen units'].sum()
                                                            ]]
                                                            , columns = calcOxidesColumns
                                                        )
                                                    ]
                                                    , ignore_index = True
                                                )
            # set index of table
            oxideCalc[str(index) + '-' + row['Sample Name']].set_index('Oxide', inplace=True)
            
            ###########################################
            # calculate step 4 - 6 for all minerals
            ###########################################
            
            for mineral, formula in usedMineralFormulas.items():
                # get total oxygen in mineral formula
                mineralOxygens = formula['oxygen']
                # get total oxygen units from calculation
                totalOxygenUnits = oxideCalc[str(index) + '-' + row['Sample Name']].loc['Total', 'Oxygen units']
                # calculate step 4 & 5 for this mineral and add the column
                colStep4 = []
                colStep5 = []
                for oxide in oxideList:
                    # normalized oxygen units (step 4)
                    oxideOxygenUnits = oxideCalc[str(index) + '-' + row['Sample Name']].loc[oxide, 'Oxygen units']
                    normalizedOxideOxygenUnits = (oxideOxygenUnits/totalOxygenUnits)*mineralOxygens
                    colStep4 = colStep4 + [normalizedOxideOxygenUnits]
                    # atom units (step 5)
                    atomUnits = normalizedOxideOxygenUnits * (oxideList[oxide]['elementCount'] / oxideList[oxide]['oxygenCount']) if oxide != 'Total' and 'O' in oxide else ('' if oxide == 'Total' else normalizedOxideOxygenUnits)
                    colStep5 = colStep5 + [atomUnits]
                # append calculated mineral columns to dataframe
                oxideCalc[str(index) + '-' + row['Sample Name']].insert(len(oxideCalc[str(index) + '-' + row['Sample Name']].columns), 'Normalized oxygen units for ' + mineral, colStep4)
                oxideCalc[str(index) + '-' + row['Sample Name']].insert(len(oxideCalc[str(index) + '-' + row['Sample Name']].columns), 'Atom units for ' + mineral, colStep5)
                
                ##########################################################
                # step 6: fill elements in formula by priority of sites
                ##########################################################
                
                # copy values from step 5 for calculations
                atomUnitsCalculated = dict(zip(oxideCalc[str(index) + '-' + row['Sample Name']]['Element'], oxideCalc[str(index) + '-' + row['Sample Name']]['Atom units for ' + mineral]))
                del atomUnitsCalculated['']
                
                # for output
                formulaFilled = copy.deepcopy(formula['formulaElements'])
             
                # make element list for loop                                    
                els = []
                seen = set() # keep track of elements already seen
                for site in reversed(formula['formulaElements']): ############## todo: --> prioSite
                    els.extend(site['elements'].keys())
                els = [x for x in els if x not in seen and not seen.add(x)] # only keep unique elements
                #els = [x for x in els if x != 'Fe'] + ['Fe'] # move 'Fe' to end
                # loop trough all elements
                for element in els:
                    # skip element if not measured
                    if element not in atomUnitsCalculated:
                        continue
                    
                    # sort sites by prioEl for this element
                    siteOrder = []
                    for no, site in enumerate(formulaFilled):
                        if element in site['elements']:
                            siteOrder.append(no)
                    siteOrder.sort(key=lambda x: formulaFilled[x]['elements'][element]['prioEl'])
                    
                    # fill sites with element by siteOrder
                    for site in siteOrder:
                        # cntSiteAvailable = cntSite - sum of all cntEl
                        cntSiteAvailable = formulaFilled[site]['cntSite'] - sum([el['cntEl'] for el in formulaFilled[site]['elements'].values()])
                        if atomUnitsCalculated[element] > 0 and cntSiteAvailable > 0:
                            # fill site if possible and update formulaFilled
                            if cntSiteAvailable <= atomUnitsCalculated[element]:
                                formulaFilled[site]['elements'][element]['cntEl'] = cntSiteAvailable
                            else:
                                formulaFilled[site]['elements'][element]['cntEl'] = atomUnitsCalculated[element]
                            # update data
                            atomUnitsCalculated[element] = atomUnitsCalculated[element] - formulaFilled[site]['elements'][element]['cntEl']
                        else:
                            continue
                # clean up formulaFilled
                for k in formulaFilled:
                    k.pop('prioSite', None)
                    for j in k['elements']:
                        k['elements'][j] = k['elements'][j]['cntEl']
                        
                ###################################
                # step 7: calculate probability
                ###################################
                # get % filled
                sumSites = 0
                sumCnts = 0
                for site in formulaFilled:
                    sumSites = sumSites + sum(site['elements'].values())
                    sumCnts = sumCnts + site['cntSite']       
                percentFilled = 100 / sumCnts * sumSites  
         
                # get % remaining elements
                sumUnmatching = sum(atomUnitsCalculated.values())
                sumAll = sumSites + sumUnmatching
                percentRemaining = 100 / sumAll * sumUnmatching
                
                # calculate weighted mean of percentFilled and percentRemaining (giving percentRemaining more weight)
                probability = (1*percentFilled + 1.5*(100-percentRemaining)) / 2.5
                    
                # save formulaFilled in output                       
                filledFormulas[str(index) + '-' + row['Sample Name']][mineral] = {'probability': probability, 'formulaFilled': formulaFilled, 'percentFilled': percentFilled, 'elementsRemaining': atomUnitsCalculated, 'percentRemaining': percentRemaining}
                
    return filledFormulas

# calculate probabilities
def calcProbabilities(filledFormulas, selectedData):
    with st.spinner('Mineral probability calculation, please wait...'):       
        #####################
        # step 8: output
        #####################
        csvMergedMinerals = copy.deepcopy(selectedData)
        # sort by probability
        prob = {}
        for sample in filledFormulas:
            prob[sample] = []
            for mineral in filledFormulas[sample]:
                # combine mineral formula as string
                txtStr = '' 
                for site in filledFormulas[sample][mineral]['formulaFilled']:
                    elementsSite =  dict(sorted(site['elements'].items(), key=lambda x: x[1], reverse=True))
                    cntSite = site['cntSite']
                    # get no of elements per site:
                    noElements = 0
                    for value in elementsSite.values():
                        if float(round(value,2)) >= 0.01:
                            noElements += 1
                    # add brackets around site if more than 1 element
                    if noElements > 1:
                        txtStr = txtStr + '('
                        
                    for element in elementsSite:
                        if float(round(elementsSite[element],2)) >= 0.01:
                            if float(round(elementsSite[element],2)) == 1.00:
                                txtStr = txtStr + element
                            else:
                                # element and value
                                txtStr = txtStr + element + ' ' + str(int(round(elementsSite[element],2))) + ', ' if float(round(elementsSite[element],2)).is_integer() else txtStr + element + ' ' + str(float(round(elementsSite[element],2))) + ', '
                    
                    if noElements > 1:
                        if float(round(sum(elementsSite.values()),2)) == 1.00:
                            txtStr = txtStr + ')'
                        else:
                            # sum of site
                            txtStr = txtStr + ')' + str(int(round(sum(elementsSite.values()),2))) if float(round(sum(elementsSite.values()),2)).is_integer() else txtStr + ')' + str(float(round(sum(elementsSite.values()),2)))
                    
                # add oxygen
                txtStr = txtStr + 'O' + str(standardMineralFormulas[mineral]['oxygen'])
                
                # probability
                prob[sample] = prob[sample] + [[mineral, txtStr, filledFormulas[sample][mineral]]]
            prob[sample] = sorted(prob[sample], key=lambda x: x[2]['probability'], reverse=True)
            #prob[sample][3]['formulaFilled']
        
        # get 1st & 2nd highest probability for every sample
        min1 = []
        min2 = []
        formula1string = []
        formula1export = []
        formula2string = []
        formula2export = []
        for sample in filledFormulas:
            min1 = min1 + [prob[sample][0][0] + ' (' + str(float(round(prob[sample][0][2]['probability'],2))) + ' %)']
            min2 = min2 + [prob[sample][1][0] + ' (' + str(float(round(prob[sample][1][2]['probability'],2))) + ' %)']
            formula1string = formula1string + [toSubscript(prob[sample][0][1])]
            formula1export = formula1export + [prob[sample][0][1]]
            formula2string = formula2string + [toSubscript(prob[sample][1][1])]
            formula2export = formula2export + [prob[sample][1][1]]
            
        csvMergedMinerals.insert(1, '1st predicted mineral', min1)
        csvMergedMinerals.insert(2, '1st mineral formula', formula1string)
        csvMergedMinerals.insert(3, '1st mineral formula_export', formula1export)
        csvMergedMinerals.insert(4, '2nd predicted mineral', min2)
        csvMergedMinerals.insert(5, '2nd mineral formula', formula2string)
        csvMergedMinerals.insert(6, '2nd mineral formula_export', formula2export)
        
    return csvMergedMinerals

## diagrams

# extract element values from mineral formula
def getTernaryPlotValues(mineral, elementA, elementB, elementC):
    ## 1st predicted mineral
    # get all points for all samples as dicts and store them in pointsList
    pointsList1 = []
    for _, row1 in sst.csvMergedMinerals.iterrows():
        # plot only Pyroxenes
        if mineral in row1['1st predicted mineral']:
            # split formula in element-value-pairs
            elementValuePairs1 = re.findall(r'(?:,\s)?([A-Z][a-z]?)\s?(\d+(?:\.\d+)?)?', row1['1st mineral formula_export'])
            # save element-value-pairs in dict
            dataElementValue1 = {}
            dataElementValue1['label'] = '<b>' + str(row1['Sample Name']) + '</b><br>' + str(row1['1st mineral formula'])
            for elementValuePair in elementValuePairs1:
                element = elementValuePair[0]
                value = float(elementValuePair[1]) if elementValuePair[1] else float(1)
                # add only Ca, Mg, Fe for plot
                if element in [elementA, elementB, elementC]:
                    # add values if element is already present
                    if element in dataElementValue1:
                        dataElementValue1[element] = float(dataElementValue1[element]) + value
                    else:
                        dataElementValue1[element] = value
    
            # append dict to list
            pointsList1.append(dataElementValue1)
    # combine all dicts into a df
    pointsCombined1 = pd.DataFrame(pointsList1)
    for element in [elementA, elementB, elementC]:
        if element not in pointsCombined1.columns:
            pointsCombined1[element] = None
    # normalize values
    #pointsCombined1 = pointsCombined1.fillna(0).apply(lambda row: row / row.sum(), axis=1) * 100
    pointsCombined1[[elementA, elementB, elementC]] = pointsCombined1[[elementA, elementB, elementC]].fillna(0).div(pointsCombined1[[elementA, elementB, elementC]].sum(axis=1), axis=0) * 100
    
    ## 2nd predicted mineral
    # get all points for all samples as dicts and store them in pointsList
    pointsList2 = []
    for _, row2 in sst.csvMergedMinerals.iterrows():
        # plot only Pyroxenes
        if mineral in row2['2nd predicted mineral']:
            # split formula in element-value-pairs
            elementValuePairs2 = re.findall(r'(?:,\s)?([A-Z][a-z]?)\s?(\d+(?:\.\d+)?)?', row2['2nd mineral formula_export'])
            # save element-value-pairs in dict
            dataElementValue2 = {}
            dataElementValue2['label'] = '<b>' + str(row2['Sample Name']) + '</b><br>' + str(row2['1st mineral formula'])
            for elementValuePair in elementValuePairs2:
                element = elementValuePair[0]
                value = float(elementValuePair[1]) if elementValuePair[1] else float(1)
                # add only Ca, Mg, Fe for plot
                if element in [elementA, elementB, elementC]:
                    # add values if element is already present
                    if element in dataElementValue2:
                        dataElementValue2[element] = float(dataElementValue2[element]) + value
                    else:
                        dataElementValue2[element] = value
            # append dict to list
            pointsList2.append(dataElementValue2)
    # combine all dicts into a df
    pointsCombined2 = pd.DataFrame(pointsList2)
    for element in [elementA, elementB, elementC]:
        if element not in pointsCombined2.columns:
            pointsCombined2[element] = None
    # normalize values
    # pointsCombined2 = pointsCombined2.fillna(0).apply(lambda row: row / row.sum(), axis=1) * 100
    pointsCombined2[[elementA, elementB, elementC]] = pointsCombined2[[elementA, elementB, elementC]].fillna(0).div(pointsCombined2[[elementA, elementB, elementC]].sum(axis=1), axis=0) * 100
    
    return pointsCombined1, pointsCombined2

# make ternary scatter plot with plotly and return fig
def makeTernaryPlot(pointsCombined1, pointsCombined2, elementA, elementB, elementC, labelA, labelB, labelC):        
    # ternary scatter plot
    if len(pointsCombined1) > 1 or len(pointsCombined2) > 1:
        fig = go.Figure()
        ######## loop
        # 1st predicted minerals
        if len(pointsCombined1) > 1:
            fig.add_trace(go.Scatterternary(
                a = pointsCombined1[elementA],
                b = pointsCombined1[elementB],
                c = pointsCombined1[elementC],
                mode = 'markers',
                marker = dict(symbol='circle', size=10, color='rgba(131, 201, 255, 0.5)', line=dict(color='rgb(131, 201, 255)', width=1)),
                cliponaxis = False,
                name = '1st predicted mineral<br>(' + str(len(pointsCombined1)) + ' samples shown)',
                hovertemplate = '%{text}<br><br><b>' + elementA + ':</b> %{a}<br><b>' + elementB + ':</b> %{b}<br><b>' + elementC + ':</b> %{c}',
                text = pointsCombined1['label']
            ))
        if len(pointsCombined2) > 1:
            # 2nd predicted minerals
            fig.add_trace(go.Scatterternary(
                a = pointsCombined2[elementA],
                b = pointsCombined2[elementB],
                c = pointsCombined2[elementC],
                mode = 'markers',
                marker = dict(symbol='circle', size=10, color='rgba(0, 104, 201, 0.5)', line=dict(color='rgb(0, 104, 201)', width=1)),
                cliponaxis = False,
                name = '2nd predicted mineral<br>(' + str(len(pointsCombined2)) + ' samples shown)',
                hovertemplate = '%{text}<br><br><b>' + elementA + ':</b> %{a}<br><b>' + elementB + ':</b> %{b}<br><b>' + elementC + ':</b> %{c}',
                text = pointsCombined2['label']
            ))
         
        # axis labels and styling
        fig.update_layout(
            # axis
            ternary = dict(
                sum = 100,
                aaxis = dict(title=labelA, tickformat='.0f', tickmode='linear', tick0=0, dtick=10, ticksuffix=' %', ticklen=5, color='black', gridcolor='gray'),
                baxis = dict(title=labelB, tickformat='.0f', tickmode='linear', tick0=0, dtick=10, ticksuffix=' %', ticklen=5, color='black', gridcolor='gray'), 
                caxis = dict(title=labelC, tickformat='.0f', tickmode='linear', tick0=0, dtick=10, ticksuffix=' %', ticklen=5, color='black', gridcolor='gray')
            ),
            # style
            showlegend = True,
            legend = dict(title='Rank', font=dict(color='black')),
            height = 450,
            width = 750,
            scattermode = 'overlay',
            plot_bgcolor = 'white',
            paper_bgcolor = 'white',
            hoverlabel=dict(align='left', font=dict(color='black')),
        )
        # plotly color sequence: ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52']
        for trace in fig.data:
            trace.hoverlabel = dict(bordercolor=trace.marker.color, bgcolor=trace.marker.color)
        
        fig.update_layout(
            hoverlabel_align = 'left'
        )
    else:
        fig = None
    return fig


#########################
# sidebar
#########################
fn.renderSidebar('menuRedirect')


#########################
# minerals
#########################
st.title('Mineral Identification', anchor=False)

if not sst.kadiLoaded or sst.csvMerged.empty:
    st.info('No measurement data found in this record.', icon=fn.pageNames['import']['ico'])
else:
    tab1, tab2 = st.tabs([':material/diamond: Mineral identification', ':material/bar_chart: Ternary Diagrams'])
    
    ############################
    # Mineral identification
    ############################
    with tab1:
    
        #######################################
        # info
        #######################################    
        with st.expander('Click to view more information about **' + fn.pageNames['mineral']['name'] + '**', icon=fn.pageNames['mineral']['ico']):
            st.subheader('How are mineral formulas calculated?', anchor=False)
            #annotated_text('Site occupation and element substitutions are adapted from the MATLAB-based program', ('[MinPlot 1.1](https://github.com/MinPlot/MinPlot_Program)', ':link:', 'rgba(111, 184, 255, 0.24)'), ' and all the references listed below the table in the expander **References for this mineral calculation**. All calculations assume that total Fe is ferrous Fe²⁺.')
            st.write('Site occupation and element substitutions are adapted from the MATLAB-based program [MinPlot 1.1](https://github.com/MinPlot/MinPlot_Program) and all the references listed below the table in the expander **References for this mineral calculation**. All calculations assume that total Fe is ferrous Fe²⁺.')
            st.subheader('How are prediction values calculated?', anchor=False)
            st.markdown('The probability of predicted minerals is calculated with respect to the site occupation and the amount of available elements (measured values). These values are calculated:')
            st.markdown(
            """
            <ul>
                <li>
                    <img src="./app/static/percentFilled.png" height="20" style="margin-right: 5px; margin-left: 5px">: to what percentage could the sites be filled?
                </li>
                <li>
                    <img src="./app/static/percentUsed.png" height="20" style="margin-right: 5px; margin-left: 5px">: how many percent of the available elements could be used to fill the crystal structure?
                </li>
                <li>
                    <img src="./app/static/percentPredicted.png" height="20" style="margin-right: 5px; margin-left: 5px">: the weighted mean of <img src="./app/static/percentFilled.png" height="20" style="margin-right: 5px; margin-left: 5px"> and <img src="./app/static/percentUsed.png" height="20" style="margin-right: 5px; margin-left: 5px">, with <img src="./app/static/percentUsed.png" height="20" style="margin-right: 5px; margin-left: 5px"> assigned a higher weight:<img src="./app/static/percentPredictedFormula.png" height="45" style="margin-left: 15px">
                </li>
            </ul>
            """,unsafe_allow_html=True)
            st.write('')
        
        st.write('Select minerals that should be used for formula recalculation:')
        left, middle, right = st.columns((1, 20, 20))
        left.write('↳')
        with middle:
            selectedMinerals = st.multiselect('Minerals used for calculation', 
                                            list(standardMineralFormulas.keys()), 
                                            default = list(standardMineralFormulas.keys()) if sst.selectedMinerals == [] else sst.selectedMinerals,
                                            label_visibility = 'collapsed',
                                            key='mineralselect',
                                        )
            
        st.write('Select the data that should be used:')
        if sst.csvMergedFiltered.empty:
            sst.csvMergedFiltered = sst.csvMerged
            
        left, middle, right = st.columns((1, 20, 20))
        left.write('↳')
        with middle:
            if not sst.csvMergedFiltered.empty and 'filterColumns' in sst.dataViewerFilter and sst.dataViewerFilter['filterColumns'] != []:
                selectData = st.selectbox('Data used for calculation',
                                        ('Filtered data', 'Original data'),
                                        label_visibility = 'collapsed',
                                    )
            else:
                selectData = st.selectbox('Data used for calculation',
                                        ('Original data', 'Filtered data'),
                                        label_visibility = 'collapsed',
                                        disabled = True,
                                    )
                st.info('No filters applied. Check out ' + fn.pageNames['viewer']['ico'] + ' **' + fn.pageNames['viewer']['name'] + '** to use filtered data instead.', icon=':material/filter_alt_off:')
                                    
            if selectData == 'Filtered data':
                selectedData = sst.csvMergedFiltered
            else:
                selectedData = sst.csvMerged
        
        st.write('')
        
        
        if len(selectedMinerals) < 2:
            st.error('Please choose more than one mineral.', icon=':material/warning:')
        else:
            #######################################
            # probability calculation
            #######################################
            # get list of oxides from original data
            oxideListMeasured = [col.replace(' (wt%)','') for col in selectedData.columns if 'wt%' in col and col.replace(' (wt%)','') != 'Total']
            # set up oxide dictionary (element counts, atomic weight of formula)
            oxides = splitOxides(oxideListMeasured)
            # formula recalculation for every sample point & save as pdDataFrame
            filledFormulas = calcOxides(oxides, selectedMinerals, selectedData)
            # probability calculation
            sst.csvMergedMinerals = calcProbabilities(filledFormulas, selectedData)
            
            #######################################
            # dataframe output
            #######################################
            st.subheader('Mineral predictions for _@' + sst.recordName + '_ (' + str(len(sst.csvMergedMinerals)) + ' samples calculated)' if sst.userType != 'demo' else 'Mineral predictions for _Quantitative Demo Dataset_ (' + str(len(sst.csvMergedMinerals)) + ' samples calculated)', anchor=False)
            
            # dataframe output
            st.dataframe(sst.csvMergedMinerals,
                column_config = {
                    col: st.column_config.DatetimeColumn(col, format='DD MMM YYYY, hh:mm') if col == 'Datetime' else (None if col in ['1st mineral formula_export', '2nd mineral formula_export'] else st.column_config.Column(col)) for col in sst.csvMergedMinerals.columns.tolist()
                },
                use_container_width = True
            )
            #######################################
            # references
            #######################################
            with st.expander('References for this mineral calculation', icon=':material/dictionary:'):        
                # general references for mineral calculation
                st.markdown('**General**')
                left, middle, right = st.columns((1, 20, 20))
                left.write('↳')
                middle.markdown('Walters (2022): https://doi.org/10.2478/mipo-2022-0005')
                if not sst.selectedMinerals == []:
                    for mineral in selectedMinerals:
                        if len(standardMineralFormulas[mineral]['references']) > 0:
                            st.markdown('**' + mineral + '**')
                            left, middle, right = st.columns((1, 20, 20))
                        for reference in standardMineralFormulas[mineral]['references']:
                            left.write('↳')
                            with middle:
                                st.markdown(reference + ': ' + standardMineralFormulas[mineral]['references'][reference])
            # update reference dict
            saveReferences(selectedMinerals)
            
            st.info('Check out **' + fn.pageNames['export']['name'] + '** if you want to download this mineral predictions and references.', icon=fn.pageNames['export']['ico'])
            
            #######################################
            # chart
            #######################################
            st.subheader('Frequency of calculated minerals in _@' + sst.recordName + '_' if sst.userType != 'demo' else 'Frequency of calculated minerals in _Quantitative Demo Dataset_', anchor=False)
            
            # count minerals
            countsData = pd.DataFrame({
                                        'Mineral': [item for mineral in selectedMinerals for item in [mineral, mineral]],
                                        'Rank': [item for mineral in selectedMinerals for item in ['1st predicted mineral', '2nd predicted mineral']],
                                        'Sum of samples': [item for mineral in selectedMinerals for item in [sst.csvMergedMinerals['1st predicted mineral'].str.contains(mineral, case=False).sum(), sst.csvMergedMinerals['2nd predicted mineral'].str.contains(mineral, case=False).sum()]],
                                        })
                                        
            barChart = alt.Chart(countsData).mark_bar(cornerRadius=2).encode(
                                    x = alt.X('Mineral:N', axis=alt.Axis(labelAngle=-45)),
                                    y = 'Sum of samples:Q',
                                    xOffset = 'Rank:N',
                                    color = 'Rank:N'
                                )
            col1, col2 = st.columns(2)
            with col1:
                st.altair_chart(barChart, use_container_width=True)
                
            sst.selectedMinerals = selectedMinerals
            
    ############################
    # Figures
    ############################
    with tab2:
        st.info('Click on the entries in the "Rank" legend to hide / show the corresponding points', icon=':material/lightbulb_circle:')
        # plot ternary diagrams
        if not sst.csvMergedMinerals.empty:
            # minerals with diagram elements and endmember names
            plotMinerals = [['Olivine', 'Ca', 'Mg', 'Fe', 'Larnite Ca₂SiO₄', 'Forsterite<br>Mg₂SiO₄', 'Fayalite<br>Fe₂SiO₄'],
                            ['Pyroxene', 'Ca', 'Mg', 'Fe', 'Wollastonite Ca₂Si₂O₆', 'Enstatite<br>Mg₂Si₂O₆', 'Ferrosilite<br>Fe₂Si₂O₆'],
                            ]
            # ternary plot for each mineral
            for mineral in plotMinerals:               
                # get values for Ca, Mg, Fe
                pointsCombined1, pointsCombined2 = getTernaryPlotValues(mineral[0], mineral[1], mineral[2], mineral[3])
                # show diagram only if there is one sample point for this mineral
                if not (pointsCombined1.empty and pointsCombined2.empty):                  
                    # output
                    st.subheader(mineral[0] + ' ternary diagram for _@' + sst.recordName + '_' if sst.userType != 'demo' else mineral[0] + ' ternary diagram for _Quantitative Demo Dataset_', anchor=False)
                    fig = makeTernaryPlot(pointsCombined1, pointsCombined2, mineral[1], mineral[2], mineral[3], mineral[4], mineral[5], mineral[6])
                    if not fig == None:
                        st.plotly_chart(fig, theme=None, use_container_width=False)
         
            ######################
            # Si-Fe-Mg ternary ?
            ######################
        else:
            st.info('To view ternary plots for the predicted minerals, please perform **' + fn.pageNames['mineral']['name'] + '**', icon=fn.pageNames['mineral']['ico'])