#!/usr/bin/env python
#
# Create ERDAS Imagine file from a MRMS Raster
#
from osgeo import gdal
from osgeo import osr
import cgi
import os
from scipy.misc import imread
import numpy as np
import datetime
import sys
import zipfile

def go(valid, period):
    """ Actually do the work! """
    fn = valid.strftime(('/mesonet/ARCHIVE/data/%Y/%m/%d/'
                         +'GIS/mrms/p'+str(period)+'h_%Y%m%d%H%M.png'))
    if not os.path.isfile(fn):
        sys.stdout.write("Content-type: text/plain\n\n")
        sys.stdout.write("ERROR: Data File Not Found!")
        return
    img = imread(fn)
    size = np.shape(img)
    #print 'A', np.max(img), np.min(img), img[0,0], img[-1,-1]
    data = np.ones( size, np.uint16) * 65535
    #print '1', np.max(data), np.min(data), data[0,0]
    data = np.where( np.logical_and(img >= 125, img < 255), 
                     (180 + (img-125) / 5.0) * 10, 
                     data)
    #print '2', np.max(data), np.min(data), data[0,0]
    data = np.where( np.logical_and(img >= 25, img < 125),
                     (100 + (img-25) / 1.25) * 10,
                     data)
    #print '3', np.max(data), np.min(data), data[0,0]
    data = np.where( img < 25,
                     (img / 0.25) * 10,
                     data)
    #print '4', np.max(data), np.min(data), data[0,0]

    data = data.astype(np.uint16)
    #print '5', np.max(data), np.min(data), data[0,0]

    drv = gdal.GetDriverByName('HFA')
    outfn = "mrms_%sh_%s.img" % (period, valid.strftime("%Y%m%d%H%M"))
    ds = drv.Create(outfn, size[1], size[0], 1, 
        gdal.GDT_UInt16, options = [ 'COMPRESS=YES' ])
    proj = osr.SpatialReference()  
    proj.SetWellKnownGeogCS( "EPSG:4326" )
    ds.SetProjection( proj.ExportToWkt()  )
    ds.GetRasterBand(1).WriteArray( data )
    ds.GetRasterBand(1).SetNoDataValue(65535)
    ds.GetRasterBand(1).SetScale(0.1)
    ds.GetRasterBand(1).SetUnitType('mm')
    title = valid.strftime("%s UTC %d %b %Y")
    ds.GetRasterBand(1).SetDescription('MRMS Q3 %sHR Precip Ending %s' % (
                                                        period, title))
    # Optional, allows ArcGIS to auto show a legend
    ds.GetRasterBand(1).ComputeStatistics(True)
    # top left x, w-e pixel resolution, rotation, top left y, rotation, n-s pixel resolution
    ds.SetGeoTransform( [ -130., 0.01, 0, 
                     55.0, 0, -0.01 ] )
    # close file
    del ds

    zipfn = "mrms_%sh_%s.zip" % (period, valid.strftime("%Y%m%d%H%M"))
    z = zipfile.ZipFile(zipfn, 'w', zipfile.ZIP_DEFLATED)
    z.write(outfn)
    z.write(outfn+".aux.xml")
    z.close()

    # Send file back to client
    sys.stdout.write("Content-type: application/octet/stream\n")
    sys.stdout.write('Content-Disposition: attachment; filename=%s\n\n' % (
                                                            zipfn,))
    sys.stdout.write( open(zipfn, 'rb').read() )

    os.unlink(outfn)
    os.unlink(zipfn)
    os.unlink(outfn+".aux.xml")

if __name__ == '__main__':
    # Go Main Go
    os.chdir("/tmp")
    
    form = cgi.FieldStorage()
    year = int(form.getfirst('year', 2014))
    month = int(form.getfirst('month', 9))
    day = int(form.getfirst('day', 4))
    hour = int(form.getfirst('hour', 0))
    minute = int(form.getfirst('minute', 0))
    
    period = int(form.getfirst('period', 24))
    
    valid = datetime.datetime(year, month, day, hour, minute)
    
    go(valid, period)