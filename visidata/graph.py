from visidata import *

option('color_graph_axis', 'bold', 'color for graph axis labels')

globalCommand('.', 'vd.push(GraphSheet(sheet.name+"_graph", sheet, selectedRows or rows, keyCols, [cursorCol]))', 'graph the current column vs key columns Numeric key column is on the x-axis, while categorical key columns determin color')
globalCommand('g.', 'vd.push(GraphSheet(sheet.name+"_graph", sheet, selectedRows or rows, keyCols, numericCols(nonKeyVisibleCols)))', 'open a graph of all visible numeric columns vs key column')


def numericCols(cols):
    # isNumeric from describe.py
    return [c for c in cols if isNumeric(c)]


class InvertedCanvas(Canvas):
    commands = Canvas.commands + [
        # swap directions of up/down
        Command('move-up', 'sheet.cursorMinY += cursorHeight', 'move cursor up'),
        Command('move-down', 'sheet.cursorMinY -= cursorHeight', 'move cursor down'),

        Command('zj', 'sheet.cursorMinY -= charGridHeight', 'move cursor down one line'),
        Command('zk', 'sheet.cursorMinY += charGridHeight', 'move cursor up one line'),

        Command('J', 'sheet.cursorHeight -= charGridHeight', 'decrease cursor height'),
        Command('K', 'sheet.cursorHeight += charGridHeight', 'increase cursor height'),

        Command('zz', 'zoomTo(cursorMinX, cursorMinY, cursorMaxX, cursorMaxY)', 'set visible bounds to cursor'),
    ]

    def zoomTo(self, x1, y1, x2, y2):
        self.fixPoint(self.plotviewMinX, self.plotviewMaxY, x1, y1)
        self.zoomlevel=max(self.cursorWidth/self.gridWidth, self.cursorHeight/self.gridHeight)

    def plotpixel(self, x, y, attr, row=None):
        y = self.plotviewMaxY-y+4
        self.pixels[round(y)][round(x)][attr].append(row)

    def scaleY(self, grid_y):
        'returns canvas y coordinate, with y-axis inverted'
        canvas_y = super().scaleY(grid_y)
        return (self.plotviewMaxY-canvas_y+4)

    def gridY(self, canvas_y):
        return (self.plotviewMaxY-canvas_y)/self.yScaler

    def fixPoint(self, canvas_x, canvas_y, grid_x, grid_y):
        'adjust visible so that (grid_x, grid_y) is plotted at (canvas_x, canvas_y)'
        self.visibleMinX = grid_x - self.gridW(canvas_x-self.plotviewMinX)
        self.visibleMinY = grid_y - self.gridH(self.plotviewMaxY-canvas_y)
        self.refresh()

    @property
    def canvasMouseY(self):
        return self.visibleMinY + (self.plotviewMaxY-self.plotterMouseY)/self.yScaler

    @property
    def cursorPixelBounds(self):
        x1, y1, x2, y2 = super().cursorPixelBounds
        return x1, y2, x2, y1  # reverse top/bottom

    @property
    def visiblePixelBounds(self):
        'invert y-axis'
        return [ self.scaleX(self.visibleMinX),
                 self.scaleY(self.visibleMaxY),
                 self.scaleX(self.visibleMaxX),
                 self.scaleY(self.visibleMinY),
        ]


# provides axis labels, legend
class GraphSheet(InvertedCanvas):
    def __init__(self, name, sheet, rows, xcols, ycols, **kwargs):
        super().__init__(name, sheet, sourceRows=rows, **kwargs)

        self.xcols = xcols
        self.ycols = [ycol for ycol in ycols if isNumeric(ycol)] or error('%s is non-numeric' % '/'.join(yc.name for yc in ycols))

    @async
    def reload(self):
        nerrors = 0
        nplotted = 0

        self.gridpoints.clear()
        self.reset()

        status('loading data points')
        catcols = [c for c in self.xcols if not isNumeric(c)]
        numcol = numericCols(self.xcols)[0]
        for ycol in self.ycols:
            for rownum, row in enumerate(Progress(self.sourceRows)):  # rows being plotted from source
                try:
                    k = tuple(c.getValue(row) for c in catcols) if catcols else (ycol.name,)
                    attr = self.plotColor(k)

                    # convert deliberately to float (to e.g. linearize date)
                    graph_x = float(numcol.type(numcol.getValue(row))) if self.xcols else rownum
                    graph_y = ycol.type(ycol.getValue(row))

                    self.point(graph_x, graph_y, attr, row)
                    nplotted += 1
                except Exception:
                    nerrors += 1
                    if options.debug:
                        raise


        status('loaded %d points (%d errors)' % (nplotted, nerrors))

        self.setZoom(1.0)
        self.refresh()

    def setZoom(self, zoomlevel=None):
        super().setZoom(zoomlevel)
        self.createLabels()

    def add_y_axis_label(self, frac):
        amt = self.visibleMinY + frac*(self.visibleHeight)
        if isinstance(self.gridMinY, int):
            txt = '%d' % amt
        elif isinstance(self.gridMinY, float):
            txt = '%.02f' % amt
        else:
            txt = str(frac)

        # plot y-axis labels on the far left of the canvas, but within the plotview height-wise
        attr = colors[options.color_graph_axis]
        self.plotlabel(0, self.plotviewMinY + (1.0-frac)*self.plotviewHeight, txt, attr)

    def add_x_axis_label(self, frac):
        amt = self.visibleMinX + frac*self.visibleWidth
        txt = ','.join(xcol.format(xcol.type(amt)) for xcol in self.xcols if isNumeric(xcol))

        # plot x-axis labels below the plotviewMaxY, but within the plotview width-wise
        attr = colors[options.color_graph_axis]
        self.plotlabel(self.plotviewMinX+frac*self.plotviewWidth, self.plotviewMaxY+4, txt, attr)

    def plotAll(self):
        super().plotAll()

    def createLabels(self):
        self.gridlabels = []

        # y-axis
        self.add_y_axis_label(1.00)
        self.add_y_axis_label(0.75)
        self.add_y_axis_label(0.50)
        self.add_y_axis_label(0.25)
        self.add_y_axis_label(0.00)

        # x-axis
        self.add_x_axis_label(1.00)
        self.add_x_axis_label(0.75)
        self.add_x_axis_label(0.50)
        self.add_x_axis_label(0.25)
        self.add_x_axis_label(0.00)

        # TODO: if 0 line is within visible bounds, explicitly draw the axis
        # TODO: grid lines corresponding to axis labels

        xname = ','.join(xcol.name for xcol in self.xcols if isNumeric(xcol)) or 'row#'
        self.plotlabel(0, self.plotviewMaxY+4, '%*s»' % (int(self.leftMarginPixels/2-2), xname), colors[options.color_graph_axis])
