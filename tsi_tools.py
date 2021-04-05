#-------------------------------------------------------------------------------
# Name:          tsi_tools.py
#
# Purpose:       This module contains several functions for calculating the
#                terrain shape index (TSI) as defined by Henry McNab. The
#                functions take the plot locations and create cardinal and
#                sub-cardinal points, extract elevation from a supplied
#                raster file, and calculate the TSI values for each of the
#                given plot centers. TSI is added the attributes of the original
#                plot point shapefile.
#
#                tsi_tools.py is intended to be an imported module, but contains
#                code to allow stand-alone runs. Syntax for stand-alone runs is
#                below:
#
# Usage:         <plots shapefile> <desired radius> <elevation raster>
#                <cardinal points output>
#
# Author:        Henry Pelfrey
# Created:       24/04/2020
#-------------------------------------------------------------------------------
import sys
import os
import math
import arcpy
import traceback

arcpy.env.workspace = os.path.dirname(sys.argv[0])
arcpy.env.overwriteOutput = True


# printArc() function from pg 453 of 'Python For ArcGIS'
def printArc(message):
    '''Print message for Script Tool and standard output'''
    print message
    arcpy.AddMessage(message)


def create_cardinals(pointFile, plotRadius, outputPath):
    '''Create a new shapefile of cardinal/subcardinal points for the input
    point file. Points are offset by the plot radius.'''

    dsc = arcpy.Describe(pointFile)
    outputDir = os.path.dirname(outputPath)
    outputFile = os.path.basename(outputPath)
    subOffset = (math.cos(math.radians(45)))*plotRadius

    arcpy.CreateFeatureclass_management(outputDir, outputFile, 'POINT', spatial_reference = dsc.spatialReference)

    try:
        cursor = arcpy.da.SearchCursor(pointFile, ['FID', 'SHAPE@XY'])
        for row in cursor:
            fid = row[0]
            coordX = row[1][0]
            coordY = row[1][1]

            try:
                insertCursor = arcpy.da.InsertCursor(outputPath, ['SHAPE@XY', 'Id'])

                northRow = [arcpy.Point(coordX, coordY + plotRadius), fid]
                insertCursor.insertRow(northRow)

                southRow = [arcpy.Point(coordX, coordY - plotRadius), fid]
                insertCursor.insertRow(southRow)

                eastRow = [arcpy.Point(coordX + plotRadius, coordY), fid]
                insertCursor.insertRow(eastRow)

                westRow = [arcpy.Point(coordX - plotRadius, coordY), fid]
                insertCursor.insertRow(westRow)

                neRow = [arcpy.Point(coordX + subOffset, coordY + subOffset), fid]
                insertCursor.insertRow(neRow)

                seRow = [arcpy.Point(coordX + subOffset, coordY - subOffset), fid]
                insertCursor.insertRow(seRow)

                nwRow = [arcpy.Point(coordX - subOffset, coordY + subOffset), fid]
                insertCursor.insertRow(nwRow)

                swRow = [arcpy.Point(coordX - subOffset, coordY - subOffset), fid]
                insertCursor.insertRow(swRow)

                del insertCursor
            except:
                printArc('An error occurred:')
                traceback.print_exc()
                del insertCursor

        del cursor
    except:
        printArc('An error occurred:')
        traceback.print_exc()
        del cursor

    printArc('{} created'.format(outputFile))
    return outputPath


def extract_elevation(pointFile, elevationRaster):
    '''Extract the raster value at each point's XY position and add it to a new
    field, RasElev'''

    arcpy.AddField_management(pointFile, 'RasElev', 'DOUBLE')
    try:
        cursor = arcpy.da.UpdateCursor(pointFile, ['FID', 'SHAPE@XY', 'RasElev'])
        for row in cursor:
            coordString = '{0} {1}'.format(row[1][0], row[1][1])
            rasterValue = float(str(arcpy.GetCellValue_management(elevationRaster, coordString)))
            row[2] = rasterValue
            cursor.updateRow(row)
        del cursor
    except:
        printArc('An error occurred:')
        traceback.print_exc()
        del cursor
    printArc('Elevation values from {} added to {}'.format(elevationRaster, pointFile))


def raster_extract(pointFile, elevationRaster):
    '''Check if the given point file and raster have the same spatial
    reference. If they do, call extract_elevation. If they do not, project the
    raster in the reference of the point file and call extract_elevation.'''

    if arcpy.Describe(pointFile).spatialReference.name == arcpy.Describe(elevationRaster).spatialReference.name:
        extract_elevation(pointFile, elevationRaster)
    else:
        outRaster = 'outraster.tif'
        arcpy.ProjectRaster_management(elevationRaster, outRaster, arcpy.Describe(pointFile).spatialReference)
        extract_elevation(pointFile, outRaster)
        arcpy.Delete_management(outRaster)


def calculate_zhat(pointFile, cardinalFile):
    '''Calculate z-hat values for each plot point. *REQUIRES* elevation values
    for each point in field named RasElev'''

    ofids = [row[1] for row in arcpy.da.SearchCursor(cardinalFile, ['FID', 'Id', 'RasElev'])]
    unique_ofids = list(set(ofids))
    pointElevs = [row[1] for row in arcpy.da.SearchCursor(pointFile, ['Id', 'RasElev'])]

    arcpy.AddField_management(pointFile, 'ZHat', 'DOUBLE')

    for i in unique_ofids:
            cardElevs = [row[1]-pointElevs[i] for row in arcpy.da.SearchCursor(cardinalFile, ['Id', 'RasElev'], "Id = {}".format(i))]
            zhat = sum(cardElevs)/len(cardElevs)
            try:
                cursor = arcpy.da.UpdateCursor(pointFile, ['FID', 'Zhat'], "FID = {}".format(i))
                for row in cursor:
                    row[1] = zhat
                    cursor.updateRow(row)
                del cursor
            except:
                printArc('An error occurred:')
                traceback.print_exc()
                del cursor
    printArc('Z-Hat values for {} calculated'.format(pointFile))


def calculate_tsi(pointFile, plotRadius):
    '''Calculate TSI values for each plot point. *REQUIRES* z-hat values in field
    named Zhat'''

    arcpy.AddField_management(pointFile, 'TSI', 'DOUBLE')
    try:
        cursor = arcpy.da.UpdateCursor(pointFile, ['Zhat', 'TSI'])
        for row in cursor:
            row[1] = row[0]/float(plotRadius)
            cursor.updateRow(row)
        del cursor
    except:
        printArc('An error occurred:')
        traceback.print_exc()
        del cursor
    printArc('TSI values for {} calculated'.format(pointFile))


if __name__ == '__main__':
    inputPlots = sys.argv[1]
    inputRadius = float(sys.argv[2])
    inputRaster = sys.argv[3]
    outputCardinals = sys.argv[4]

    create_cardinals(inputPlots, inputRadius, outputCardinals)

    raster_extract(inputPlots, inputRaster)
    raster_extract(outputCardinals, inputRaster)

    calculate_zhat(inputPlots, outputCardinals)

    calculate_tsi(inputPlots, inputRadius)