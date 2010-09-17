#
# shapefile.py
#
# SVN/CVS Keywords
#------------------------------
# $Author$
# $Date$
# $Revision$
#------------------------------
#
# Original version by Zachary Forest Johnson
# http://indiemaps.com/blog/index.php/code/pyShapefile.txt
#
# Modified version by Michael Geary
# http://code.google.com/p/primary-maps-2008/source/browse/trunk/shpUtils.py
#
# This version by Carl J. Nobile
#

from struct import unpack
import dbfUtils


class ShapeFile(object):
    """
    This class supplies methods to parse shape files and returns a dict of its
    data.

    The shape file spec 'ESRI Shapefile Technical Description' found at
    http://www.esri.com/library/whitepapers/pdfs/shapefile.pdf is partially
    supported.

    The following shapes are supported:
    NullShape, Point, PolyLine, Polygon, and MultiPoint.

    The following shapes are not supported:
    PointZ, PolyLineZ, PolygonZ, MultiPointZ, PointM, PolyLineM, PolygonM,
    MultiPointM, and MultiPatch.
    """
    __slots__ = ('__BIG_ENDIAN_UNSIGNED_LONG', '__LITTLE_ENDIAN_UNSIGNED_LONG',
                 '__db', '__pointCount', '__readMethods',)
    __BIG_ENDIAN_UNSIGNED_LONG = ">L"
    __LITTLE_ENDIAN_UNSIGNED_LONG = "<L"
    __db = []

    def __init__(self):
        self.__pointCount = 0

    def loadShapefile(self, filename):
        # Open dbf file and get features as a list.
        dbfile = open(filename[0:-4] + '.dbf', 'rb')
        self.__db[:] = list(dbfUtils.dbfreader(dbfile))
        dbfile.close()

        # Get basic shapefile configuration.
        fp = open(filename, 'rb')
        fp.seek(32)
        filetype = self._readAndUnpack('i', fp.read(4))
        bounds = self._readBounds(fp)

        # Fetch Records.
        fp.seek(100)
        features = []

        while True:
            feature = self._createRecord(fp)
            if not feature: break
            self._processPolyInfo(feature)
            features.append(feature)

        return {'type': filetype, 'bounds': bounds, 'features': features}

    def _createRecord(self, fp):
        result = None
        # Read header
        recordNumber = self._readAndUnpack(
            self.__BIG_ENDIAN_UNSIGNED_LONG, fp.read(4))

        if recordNumber != '':
            contentLength = self._readAndUnpack(
                self.__BIG_ENDIAN_UNSIGNED_LONG, fp.read(4))
            recType = self._readAndUnpack(
                self.__LITTLE_ENDIAN_UNSIGNED_LONG, fp.read(4))
            #print recordNumber, contentLength, recType
            shape = self.__readMethods[recType][0](self, fp)

            if shape:
                shape['type'] = recType
                info = {}
                names = self.__db[0]
                values = self.__db[recordNumber + 1]

                for i in xrange(len(names)):
                    value = values[i]

                    if isinstance(value, str):
                        value = value.strip()
                        info[names[i]] = value

                result = {'shape': shape, 'info': info}
            else:
                msg = "Found unsupported record type: %s: %s"
                raise NotImplementedError(
                    msg % (recType, self.__readMethods[recType][1]))

        return result

    def _readRecordNull(self, fp):
        return {}

    def _readRecordPoint(self, fp):
        point = {'points': (self._readAndUnpack('d', fp.read(8)),
                            self._readAndUnpack('d', fp.read(8)))}
        self.__pointCount += 1
        return point

    def _readRecordPolyLine(self, fp):
        shape = {'bounds': self._readBounds(fp)}
        nParts = self._readAndUnpack('i', fp.read(4))
        nPoints = self._readAndUnpack('i', fp.read(4))

        if self._readAndUnpack('i', fp.read(4)) != 0:
            raise ValueError('ERROR: First part offset must be 0')

        counts = []
        prev = 0

        for i in xrange(nParts - 1):
            nextItem = self._readAndUnpack('i', fp.read(4))
            counts.append(nextItem - prev)
            prev = nextItem

        counts.append(nPoints - prev)
        parts = shape['parts'] = []

        for i in xrange(nParts):
            part = {}
            parts.append(part)
            points = part['points'] = []

            for j in xrange(counts[i]):
                points.append(self._readRecordPoint(fp))

        return shape

    def _readRecordMultiPoint(self, fp):
        shape = {'bounds': self._readBounds(fp)}
        points = shape['points'] = []
        nPoints = self._readAndUnpack('i', fp.read(4))

        for i in xrange(nPoints):
            points.append(self._readRecordPoint(fp))

        return shape

    __readMethods = {
        0: (_readRecordNull, 'NullShape'),
        1: (_readRecordPoint, 'Point'),
        3: (_readRecordPolyLine, 'PolyLine'),
        5: (_readRecordPolyLine, 'Polygon'),
        8: (_readRecordMultiPoint, 'MultiPoint'),
        11: (None, 'PointZ'),
        13: (None, 'PolyLineZ'),
        15: (None, 'PolygonZ'),
        18: (None, 'MultiPointZ'),
        21: (None, 'PointM'),
        23: (None, 'PolyLineM'),
        25: (None, 'PolygonM'),
        28: (None, 'MultiPointM'),
        31: (None, 'MultiPatch'),
        }

    def _readBounds(self, fp):
        return (
            (self._readAndUnpack('d',fp.read(8)),
             self._readAndUnpack('d',fp.read(8))),
            (self._readAndUnpack('d',fp.read(8)),
             self._readAndUnpack('d',fp.read(8)))
            )

    def _readAndUnpack(self, fieldtype, data):
        if data != '': data = unpack(fieldtype, data)[0]
        return data

    def _processPolyInfo(self, feature):
        nPoints = cx = cy = 0
        shape = feature['shape']
        shapeType = shape['type']

        if shapeType in (3, 5):
            for part in shape['parts']:
                self._processPartInfo(part)

    def _processPartInfo(self, part):
        points = [points['points'] for points in part['points']]
        n = len(points)
        area = cx = cy = 0
        xmin = ymin = 360
        xmax = ymax = -360
        pt = points[n-1]
        xx = pt[0]
        yy = pt[1]

        for pt in points:
            x = pt[0];  y = pt[1]
            # Bounds
            xmin = min(x, xmin)
            ymin = min(y, ymin)
            xmax = max(x, xmax)
            ymax = max(y, ymax)
            # Area and centroid
            a = xx * y - x * yy
            area += a
            cx += (x + xx) * a
            cy += (y + yy) * a
            # Next
            xx = x
            yy = y
            area /= 2

        if area:
            centroid = (cx / area / 6, cy / area / 6)
        else:
            centroid = None

        part.update({
            'area': abs(area),
            'bounds': ((xmin, ymin), (xmax, ymax)),
            'center': ((xmin + xmax) / 2, (ymin + ymax) / 2),
            'centroid': centroid,
            'extent': (abs(xmax - xmin), abs(ymax - ymin))
            })

    def _processBoundCenters(self, features):
        for feature in features:
            bounds = feature['shape']['bounds']
            min = bounds[0]
            max = bounds[1]
            bounds['center'] = ((min[0] + max[0]) / 2,
                                (min[1] + max[1]) / 2)

    def getMAT(self, features):
        raise NotImplementedError('Feature not implimented yet.')

    def dumpFeatureInfo(self, features):
        fields = []
        rows = []

        for feature in features:
            info = feature['info']

            if not len(fields):
                for key in info:
                    fields.append(key)

                rows.append(','.join(fields))

            cols = []

            for field in fields:
                cols.append(str(feature['info'][field]))

            rows.append(','.join(cols))

        return '\r\n'.join(rows)
