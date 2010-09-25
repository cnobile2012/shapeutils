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
    NullShape, Point, PolyLine, Polygon, MultiPoint, PointM.

    The following shapes are not supported:
    PointZ, PolyLineZ, PolygonZ, MultiPointZ, PolyLineM, PolygonM, MultiPointM,
    and MultiPatch.
    """
    __slots__ = ('__LE_SINT', '__BE_SINT', '__LE_DOUBLE', '__db',
                 '__readMethods',)
    __LE_SINT = '<i'
    __BE_SINT = '>i'
    __LE_DOUBLE = '<d'
    __db = []

    def parse(self, filename):
        # Get basic shapefile configuration.
        fp = open(filename, 'rb')

        if self._readAndUnpack(self.__BE_SINT, fp.read(4)) != 9994:
            raise ValueError("Invalid or corrupted shapefile.")

        # Open dbf file and get features as a list.
        dbfile = open(filename[0:-4] + '.dbf', 'rb')
        self.__db[:] = list(dbfUtils.dbfreader(dbfile))
        dbfile.close()

        fp.seek(32)
        shapeType = self._readAndUnpack(self.__LE_SINT, fp.read(4))
        # Get surface bounds.
        bounds = self._readBounds(fp)
        # Get Z (axis) and M (measure) bounds if any.
        bounds += self._readBounds(fp)

        # Fetch Records.
        features = []

        while True:
            feature = self._createRecord(fp)
            if not feature: break

            if shapeType in (3, 5, 23, 25):
                self._processPolyInfo(feature)

            features.append(feature)

        return {'type': shapeType, 'bounds': bounds, 'features': features}

    def _createRecord(self, fp):
        result = None
        # Read header
        recordNumber = self._readAndUnpack(self.__BE_SINT, fp.read(4))

        if recordNumber != '':
            contentLength = self._readAndUnpack(self.__BE_SINT, fp.read(4))
            recType = self._readAndUnpack(self.__LE_SINT, fp.read(4))
            #print recordNumber, contentLength, recType
            # Read content
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
        """
        Type: 0
        """
        return {}

    def _readRecordPoint(self, fp):
        """
        Type: 1

        Point {
          Double    X    // X Coordinate
          Double    Y    // Y Coordinate
        }
        """
        return {'points': self._readPoint(fp)}

    def _readRecordPoly(self, fp):
        """
        Type: 3 and 5

        PolyLine {
          Double[4]         Box        // Bounding Box (Xmin, Ymin, Xmax, Ymax)
          Integer           NumParts   // Number of Parts
          Integer           NumPoints  // Total Number of Points
          Integer[NumParts] Parts      // Index to First Point in Part
          Point[NumPoints]  Points     // Points for All Parts
        }
        """
        shape = {'bounds': self._readBounds(fp)}
        nParts = self._readAndUnpack(self.__LE_SINT, fp.read(4))
        nPoints = self._readAndUnpack(self.__LE_SINT, fp.read(4))
        offsetParts = [self._readAndUnpack(self.__LE_SINT, fp.read(4))
                       for idx in xrange(nParts)]
        size = len(offsetParts)

        for i in xrange(size):
            offset = offsetParts[i]

            if i < (size - 1):
                offsetParts[i] = offsetParts[i + 1] - offset
                nPoints -= offsetParts[i]
            else:
                offsetParts[i] = nPoints

        parts = shape['parts'] = []

        for i in xrange(nParts):
            part = {}
            parts.append(part)
            points = [self._readPoint(fp) for j in xrange(offsetParts[i])]
            self._deleteConsecutiveDuplicatePoints(points)
            part['points'] = points

        return shape

    def _readRecordMultiPoint(self, fp):
        """
        Type: 8

        MultiPoint {
          Double[4]         Box        // Bounding Box (Xmin, Ymin, Xmax, Ymax)
          Integer           NumPoints  // Number of Points
          Points[NumPoints] Points     // The Points in the Set
        }
        """
        shape = {'bounds': self._readBounds(fp)}
        nPoints = self._readAndUnpack(self.__LE_SINT, fp.read(4))
        shape['points'] = [self._readPoint(fp) for i in xrange(nPoints)]
        return shape




    def _readRecordPointM(self, fp):
        """
        Type: 21

        Point {
          Double    X    // X Coordinate
          Double    Y    // Y Coordinate
          Double    M    // Measure
        }
        """
        return {'points': self._readPointM(fp)}

    def _readRecordPolyM(self, fp):
        """
        Type: 23 and 25

        PolyLine {
          Double[4]         Box        // Bounding Box (Xmin, Ymin, Xmax, Ymax)
          Integer           NumParts   // Number of Parts
          Integer           NumPoints  // Total Number of Points
          Integer[NumParts] Parts      // Index to First Point in Part
          Point[NumPoints]  Points     // Points for All Parts
          Double[2]         M Range    // Bounding Measure Range (Mmin, Mmax)
          Double[NumPoints] M Array    // Measures
        }
        """
        shape = self._readRecordPoly(fp)
        # *** _readMeasure may not be correct. ***
        shape.update(self._readMeasure(fp))
        return shape





    def _readRecordMultiPointM(self, fp):
        """
        Type: 28

        MultiPoint {
          Double[4]         Box        // Bounding Box (Xmin, Ymin, Xmax, Ymax)
          Integer           NumPoints  // Number of Points
          Points[NumPoints] Points     // The Points in the Set
          Double[2]         M Range    // Bounding Measure Range (Mmin, Mmax)
          Double[NumPoints] M Array    // Measures
        }
        """
        shape = self._readRecordMultiPoint(fp)
        # *** _readMeasure may not be correct. ***
        shape.update(self._readMeasure(fp))
        return shape




    __readMethods = {
        0: (_readRecordNull, 'NullShape'),
        1: (_readRecordPoint, 'Point'),
        3: (_readRecordPoly, 'PolyLine'),
        5: (_readRecordPoly, 'Polygon'),
        8: (_readRecordMultiPoint, 'MultiPoint'),
        11: (None, 'PointZ'),
        13: (None, 'PolyLineZ'),
        15: (None, 'PolygonZ'),
        18: (None, 'MultiPointZ'),
        21: (_readRecordPointM, 'PointM'),
        23: (_readRecordPolyM, 'PolyLineM'),
        25: (_readRecordPolyM, 'PolygonM'),
        28: (_readRecordMultiPointM, 'MultiPointM'),
        31: (None, 'MultiPatch'),
        }

    def _readBounds(self, fp):
        return [
            (self._readAndUnpack(self.__LE_DOUBLE, fp.read(8)),
             self._readAndUnpack(self.__LE_DOUBLE, fp.read(8))),
            (self._readAndUnpack(self.__LE_DOUBLE, fp.read(8)),
             self._readAndUnpack(self.__LE_DOUBLE, fp.read(8)))
            ]

    def _readPoint(self, fp):
        return (self._readAndUnpack(self.__LE_DOUBLE, fp.read(8)),
                self._readAndUnpack(self.__LE_DOUBLE, fp.read(8)))

    def _readPointM(self, fp):
        return (self._readAndUnpack(self.__LE_DOUBLE, fp.read(8)),
                self._readAndUnpack(self.__LE_DOUBLE, fp.read(8)),
                self._readAndUnpack(self.__LE_DOUBLE, fp.read(8)))

    def _readMeasure(self, fp):
        shape = {}
        shape['mRange'] = self._readPoint(fp)
        shape['mArray'] = [self._readAndUnpack(self.__LE_DOUBLE, fp.read(8))
                           for i in xrange(nPoints)]
        return shape

    def _readAndUnpack(self, fieldtype, data):
        if data != '': data = unpack(fieldtype, data)[0]
        return data

    def _deleteConsecutiveDuplicatePoints(self, points):
        size = len(points)
        dups = []

        for i in xrange(size):
            idx = i + 1

            if idx < size and points[i] == points[idx]:
                dups.append(i)

        dups.reverse()
        return [points.pop(i) for i in dups]

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
    import sys
    sf = ShapeFile()
    print sf.parse(sys.argv[1])
