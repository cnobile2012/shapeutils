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
    http://www.esri.com/library/whitepapers/pdfs/shapefile.pdf is fully
    supported to the best of my knowledge.

    The following shapes are supported:
    NullShape, Point, PolyLine, Polygon, MultiPoint, PointZ, PolyLineZ,
    PolygonZ, MultiPointZ, PointM, PolyLineM, PolygonM, MultiPointM,
    and MultiPatch.
    """
    __slots__ = ('__LE_SINT', '__BE_SINT', '__LE_DOUBLE', '__db', '_NULL_SHAPE',
                 '_POINT', '_POLYLINE', '_POLYGON', '_MULTIPOINT',
                 '_POINT_Z', '_POLYLINE_Z', '_POLYGON_Z', '_MULTIPOINT_Z',
                 '_POINT_M', '_POLYLINE_M', '_POLYGON_M', '_MULTIPOINT_M',
                 '_MULTIPATCH', '__filename', '__contentLength', '__shapeType',
                 '__recordNum', '__readMethods',)
    __LE_SINT = '<i'
    __BE_SINT = '>i'
    __LE_DOUBLE = '<d'
    __db = []
    _NULL_SHAPE = 0
    _POINT = 1
    _POLYLINE = 3
    _POLYGON = 5
    _MULTIPOINT = 8
    _POINT_Z = 11
    _POLYLINE_Z = 13
    _POLYGON_Z = 15
    _MULTIPOINT_Z = 18
    _POINT_M = 21
    _POLYLINE_M = 23
    _POLYGON_M = 25
    _MULTIPOINT_M = 28
    _MULTIPATCH = 31

    def __init__(self, filename):
        self.__filename = filename
        self.__contentLength = 0
        self.__shapeType = 0
        self.__recordNum = 0

    def parse(self):
        # Get basic shapefile configuration.
        fp = open(self.__filename, 'rb')

        if self._readAndUnpack(self.__BE_SINT, fp.read(4)) != 9994:
            raise ValueError("Invalid or corrupted shapefile.")

        # Open dbf file and get features as a list.
        dbfile = open(self.__filename[0:-4] + '.dbf', 'rb')
        self.__db[:] = list(dbfUtils.dbfreader(dbfile))
        dbfile.close()

        fp.seek(32)
        shapeType = self._readAndUnpack(self.__LE_SINT, fp.read(4))
        self.__shapeType = shapeType
        # Get surface bounds.
        bounds = self._readBounds(fp)
        # Get Z (axis) and M (measure) bounds if any.
        bounds += self._readBounds(fp)

        # Fetch Records.
        features = []

        while True:
            feature = self._createRecord(fp, shapeType)
            if not feature: break

            if shapeType in (self._POLYLINE, self._POLYGON,
                             self._POLYLINE_Z, self._POLYGON_Z,
                             self._POLYLINE_M, self._POLYGON_M):
                self._processPolyInfo(feature)

            features.append(feature)

        return {'type': shapeType, 'bounds': bounds, 'features': features}

    def _createRecord(self, fp, shapeType):
        result = None
        # Read header
        recordNumber = self._readAndUnpack(self.__BE_SINT, fp.read(4))

        if recordNumber != '':
            self.__recordNum = recordNumber
            # Read content
            shape = self.__readMethods[shapeType][0](self, fp)

            if shape:
                shape['type'] = shapeType
                info = {}
                names = self.__db[0]
                values = self.__db[recordNumber + 1]

                for i in xrange(len(names)):
                    value = values[i]

                    if isinstance(value, str):
                        if value[0] == '\x00': value = ''
                        value = value.strip()
                        info[names[i]] = value

                result = {'shape': shape, 'info': info}
            else:
                msg = "Found unsupported record type: %s: %s"
                raise NotImplementedError(
                    msg % (shapeType, self.__readMethods[shapeType][1]))

        return result

    def _getLengthAndType(self, fp):
        contentLength = self._readAndUnpack(self.__BE_SINT, fp.read(4))
        shapeType = self._readAndUnpack(self.__LE_SINT, fp.read(4))
        self.__contentLength = 2
        #print recordNumber, contentLength, recType
        return contentLength, shapeType

    def _readRecordNull(self, fp):
        """
        Type: Null Shape (0)
        """
        contentLength, shapeType = self._getLengthAndType(fp)
        self._checkContentLength(contentLength)
        return {}

    def _readRecordPoint(self, fp):
        """
        Type: Point (1), PointZ (11), or PointM (21)

        Point {
          Double    X    // X Coordinate
          Double    Y    // Y Coordinate

          // If Z Coordinate
          Double    Z    // Z Coordinate

          // If Measure
          Double    M    // Measure
        }
        """
        contentLength, shapeType = self._getLengthAndType(fp)
        result = {}

        if shapeType == self._POINT:
            result['points'] = self._readDoubles(fp, 2)
        else:
            if shapeType == self._POINT_Z:
                result['points'] = self._readDoubles(fp, 3)

            if shapeType in (self._POINT_Z, self._POINT_M) and \
                   self.__contentLength < contentLength:
                result['measures'] = self._readDoubles(fp, 1)

        self._checkContentLength(contentLength)
        return result

    def _readRecordPoly(self, fp):
        """
        Type: PolyLine (3), Polygon (5), PolyLineZ (13), PolygonZ (15),
              PolyLineM (23), PolygonM (25), or MultiPatch (31)

        PolyLine/Polygon {
          Double[4]         Box        // Bounding Box (Xmin, Ymin, Xmax, Ymax)
          Integer           NumParts   // Number of Parts
          Integer           NumPoints  // Total Number of Points
          Integer[NumParts] Parts      // Index to First Point in Part

          // If MultiPatch
          Integer[NumParts] PartTypes  // Part Type

          Point[NumPoints]  Points     // Points for All Parts

          // If Z Coordinate
          Double[2]         Z Range    // Bounding Z Range (Zmin, Zmax)
          Double[NumPoints] Z Array    // Z Values for All Points

          // If Measure
          Double[2]         M Range    // Bounding Measure Range (Mmin, Mmax)
          Double[NumPoints] M Array    // Measures
        }
        """
        contentLength, shapeType = self._getLengthAndType(fp)
        shape = {'bounds': self._readBounds(fp)}
        nParts = self._readIntegers(fp, 1)
        nPoints = self._readIntegers(fp, 1)
        offsetParts = [self._readIntegers(fp, 1) for idx in xrange(nParts)]
        self._processOffsetParts(offsetParts, nPoints)

        if shapeType == self._MULTIPATCH:
            partTypes = [self._readIntegers(fp, 1) for idx in xrange(nParts)]

        parts = shape['parts'] = []

        for i in xrange(nParts):
            part = {}
            parts.append(part)
            points = [self._readDoubles(fp, 2) for j in xrange(offsetParts[i])]
            part['points'] = points

        if shapeType in (self._POLYLINE_Z, self._POLYGON_Z):
            shape['zRange'] = self._readDoubles(fp, 2)

            for i in xrange(nParts):
                nPointsOffset = offsetParts[i]
                part = parts[i]
                zPoints = self._readDoubles(fp, nPointsOffset)
                points = part['points']
                nPointsInPart = len(points)
                nZPoints = len(zPoints)

                if nPointsInPart != nZPoints:
                    msg = "Found %s points in part %s should be equal " + \
                          "to %s Z points."
                    raise ValueError(msg % (nPointsInPart, i, nZPoints))

                [points[i].append(self._readDoubles(fp, 1))
                 for i in xrange(nPointsInPart)]

        if shapeType in (self._POLYLINE_Z, self._POLYGON_Z,
                         self._POLYLINE_M, self._POLYGON_M) and \
                         self.__contentLength < contentLength:
            shape['mRange'] = self._readDoubles(fp, 2)

            for i in xrange(nParts):
                nPointsOffset = offsetParts[i]
                part = parts[i]
                measures = self._readDoubles(fp, nPointsOffset)
                points = part['points']
                nPointsInPart = len(points)
                nMeasures = len(measures)

                if nPointsInPart != nMeasures:
                    msg = "Found %s points in part %s should be equal " + \
                          "to %s measures."
                    raise ValueError(msg % (nPointsInPart, i, nMeasures))

                part['measure'] = measures

        self._checkContentLength(contentLength)
        self._deleteConsecutiveDuplicatePoints(parts)
        return shape

    def _readRecordMultiPoint(self, fp):
        """
        Type: MultiPoint (8), MultiPointZ (18), and MultiPointM (28)

        MultiPoint {
          Double[4]         Box        // Bounding Box (Xmin, Ymin, Xmax, Ymax)
          Integer           NumPoints  // Number of Points
          Points[NumPoints] Points     // The Points in the Set

          // If Z Coordinate
          Double[2]         Z Range    // Bounding Z Range (Zmin, Zmax)
          Double[NumPoints] Z Array    // Z values

          // If Measure
          Double[2]         M Range    // Bounding Measure Range (Mmin, Mmax)
          Double[NumPoints] M Array    // Measures
        }
        """
        contentLength, shapeType = self._getLengthAndType(fp)
        shape = {'bounds': self._readBounds(fp)}
        nPoints = self._readIntegers(fp, 1)
        points = [self._readDoubles(fp, 2) for i in xrange(nPoints)]
        shape['points'] = points

        if shapeType == self._MULTIPOINT_Z:
            shape['zRange'] = self._readDoubles(fp, 2)
            [points[i].append(self._readDoubles(fp, 1))
             for i in xrange(nPoints)]

        if shapeType in (self.MULTIPOINT_Z, self._MULTIPOINT_M) and \
               self.__contentLength < contentLength:
            shape['mRange'] = self._readDoubles(fp, 2)
            shape['measures'] = [self._readDoubles(fp, 1)
                                 for i in xrange(nPoints)]

        self._checkContentLength(contentLength)
        return shape

    __readMethods = {
        _NULL_SHAPE: (_readRecordNull, 'NullShape'),
        _POINT: (_readRecordPoint, 'Point'),
        _POLYLINE: (_readRecordPoly, 'PolyLine'),
        _POLYGON: (_readRecordPoly, 'Polygon'),
        _MULTIPOINT: (_readRecordMultiPoint, 'MultiPoint'),
        _POINT_Z: (_readRecordPoint, 'PointZ'),
        _POLYLINE_Z: (_readRecordPoly, 'PolyLineZ'),
        _POLYGON_Z: (_readRecordPoly, 'PolygonZ'),
        _MULTIPOINT_Z: (_readRecordMultiPoint, 'MultiPointZ'),
        _POINT_M: (_readRecordPoint, 'PointM'),
        _POLYLINE_M: (_readRecordPoly, 'PolyLineM'),
        _POLYGON_M: (_readRecordPoly, 'PolygonM'),
        _MULTIPOINT_M: (_readRecordMultiPoint, 'MultiPointM'),
        _MULTIPATCH: (_readRecordPoly, 'MultiPatch'),
        }

    def _readBounds(self, fp):
        return [self._readDoubles(fp, 2), self._readDoubles(fp, 2)]

    def _readIntegers(self, fp, items, type=__LE_SINT):
        result = [self._readAndUnpack(type, fp.read(4)) for i in xrange(items)]
        self.__contentLength += items * 2
        return items > 1 and result or result[0]

    def _readDoubles(self, fp, items, type=__LE_DOUBLE):
        result = [self._readAndUnpack(type, fp.read(8))
                  for i in xrange(items)]
        self.__contentLength += items * 4
        return items > 1 and result or result[0]

    def _readAndUnpack(self, fieldtype, data):
        if data != '': data = unpack(fieldtype, data)[0]
        return data

    def _processOffsetParts(self, offsetParts, nPoints):
        size = len(offsetParts)

        for i in xrange(size):
            offset = offsetParts[i]

            if i < (size - 1):
                offsetParts[i] = offsetParts[i + 1] - offset
                nPoints -= offsetParts[i]
            else:
                offsetParts[i] = nPoints

    def _deleteConsecutiveDuplicatePoints(self, parts):
        for part in parts:
            points = part.get('points')
            pSize = len(points)
            measures = part.get('measures')
            dups = []

            for i in xrange(pSize):
                idx = i + 1

                if idx < pSize and points[i] == points[idx]:
                    dups.append(i)

            dups.reverse()
            badPoints = [points.pop(i) for i in dups]
            #print >> sys.stderr, badPoints

            if measures:
                badMeasures = [measures.pop(i) for i in dups]
                #print >> sys.stderr, badMeasures

    def _checkContentLength(self, contentLength):
        if self.__contentLength != contentLength:
            msg = "Invalid content length, found %s should be %s for " + \
                  "shape type %s in record number %s."
            raise ValueError(msg % (self.__contentLength, contentLength,
                                    self.__shapeType, self.__recordNum))

    def _processPolyInfo(self, feature):
        shape = feature['shape']
        shapeType = shape['type']

        for part in shape['parts']:
            self._processPartInfo(part)

    def _processPartInfo(self, part):
        points = part['points']
        n = len(points)
        area = cx = cy = 0
        xmin = ymin = 360
        xmax = ymax = -360
        pt = points[n-1]
        xx = pt[0]
        yy = pt[1]

        for pt in points:
            x = pt[0]
            y = pt[1]
            # Bounds
            xmin = min(x, xmin)
            ymin = min(y, ymin)
            xmax = max(x, xmax)
            ymax = max(y, ymax)
            # Area and Centroid
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
            xymin = bounds[0]
            xymax = bounds[1]
            bounds['center'] = ((xymin[0] + xymax[0]) / 2,
                                (xymin[1] + xymax[1]) / 2)

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


if __name__ == '__main__':
    import sys, pprint
    sf = ShapeFile(sys.argv[1])
    pp = pprint.PrettyPrinter()
    pp.pprint(sf.parse())
