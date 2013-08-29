import sys, os, pickle
from PyQt4 import QtGui, QtCore
from obspy import read
from obspy.core import event, UTCDateTime
from itertools import cycle

import numpy as np

import matplotlib
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class streamPick(QtGui.QMainWindow):
    def __init__(self, parent=None, stream=None, picks=[]):
        qApp = QtGui.QApplication(sys.argv)

        # TMP STUFF
        if stream is None:
            msg = 'Define stream = obspy.core.Stream()'
            raise ValueError(msg)
        # Init vars
        self.st = stream
        self.picks = picks
        self.savefile = None
        # Load filters from pickle
        try:
            self.bpfilter = pickle.load(open('.pick_filters', 'r'))
        except:
            self.bpfilter = []
        # Gui vars
        self._plt_drag = None
        self._current_filter = None
        # Init stations
        self._initStations()  # defines list self._stations
        self._stationCycle = cycle(self._stations)
        self._streamStation(self._stationCycle.next())
        # Init QtGui
        QtGui.QMainWindow.__init__(self)
        self.setupUI()
        # exec QtApp
        qApp.exec_()

    def setupUI(self):
        '''
        Setup the UI
        '''
        self.main_widget = QtGui.QWidget(self)
        # Init parts of the UI
        self._initMenu()
        self._createStatusBar()
        self._initPlots()

        # Define layout
        l = QtGui.QVBoxLayout(self.main_widget)
        l.addLayout(self.btnbar)
        l.addWidget(self.canvas)

        self.setCentralWidget(self.main_widget)
        self.setGeometry(300, 300, 700, 500)
        self.setWindowTitle('PickMe')
        self.show()

    def _initPlots(self):
        self.fig = Figure(facecolor='.86', dpi=72, frameon=True)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setFocusPolicy(QtCore.Qt.StrongFocus)
        # Draw the matplotlib figure
        self._drawFig()
        # Connect the events
        self.fig.canvas.mpl_connect('scroll_event',
                                    self._pltOnScroll)
        self.fig.canvas.mpl_connect('motion_notify_event',
                                    self._pltOnDrag)
        self.fig.canvas.mpl_connect('button_release_event',
                                    self._pltOnButtonRelease)
        self.fig.canvas.mpl_connect('button_press_event',
                                    self._pltOnButtonPress)

    def _initMenu(self):
        # Next and Prev Button
        nxt = QtGui.QPushButton('Next Station >>', shortcut="d")
        nxt.clicked.connect(self._pltNextStation)
        nxt.setToolTip('shortcut <b>d</d>')
        nxt.setMaximumWidth(150)
        prv = QtGui.QPushButton('<< Prev Station', shortcut="s")
        prv.clicked.connect(self._pltPrevStation)
        prv.setToolTip('shortcut <b>s</d>')
        prv.setMaximumWidth(150)

        # Stations drop-down
        self.stcb = QtGui.QComboBox(self)
        for st in self._stations:
            self.stcb.addItem(st)
        self.stcb.activated.connect(self._pltStation)
        self.stcb.setMaximumWidth(100)
        self.stcb.setMinimumWidth(80)

        # Filter buttons
        self.fltrbtn = QtGui.QPushButton('Filter Trace', shortcut="f")
        self.fltrbtn.setToolTip('shortcut <b>f</b>')
        self.fltrbtn.setCheckable(True)
        self.fltrbtn.clicked.connect(self._appFilter)

        self.fltrcb = QtGui.QComboBox(self)
        self.fltrcb.activated.connect(self._changeFilter)
        self.fltrcb.setMaximumWidth(170)
        self.fltrcb.setMinimumWidth(150)
        self._updateFilterCB()  # fill QComboBox

        # edit/delete filer buttons
        fltredit = QtGui.QPushButton('Edit')
        fltredit.resize(fltredit.sizeHint())
        fltredit.clicked.connect(self._editFilter)

        fltrdel = QtGui.QPushButton('Delete')
        fltrdel.resize(fltrdel.sizeHint())
        fltrdel.clicked.connect(self._deleteFilter)

        btnstyle = QtGui.QFrame(fltredit)
        btnstyle.setFrameStyle(QtGui.QFrame.Box | QtGui.QFrame.Plain)
        btnstyle = QtGui.QFrame(fltrdel)
        btnstyle.setFrameStyle(QtGui.QFrame.Box | QtGui.QFrame.Plain)

        # Arrange buttons
        vline = QtGui.QFrame()
        vline.setFrameStyle(QtGui.QFrame.VLine | QtGui.QFrame.Raised)
        self.btnbar = QtGui.QHBoxLayout()
        self.btnbar.addWidget(prv)
        self.btnbar.addWidget(nxt)
        self.btnbar.addWidget(QtGui.QLabel('Select station', self))
        self.btnbar.addWidget(self.stcb)
        self.btnbar.addWidget(vline)
        self.btnbar.addWidget(self.fltrbtn)
        self.btnbar.addWidget(self.fltrcb)
        self.btnbar.addWidget(fltredit)
        self.btnbar.addWidget(fltrdel)
        self.btnbar.addStretch(3)

        # Menubar
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        saveQML = fileMenu.addAction(QtGui.QIcon().fromTheme('document-save'),
                            'Save', self._saveCatalog)
        fileMenu.addAction(QtGui.QIcon().fromTheme('document-save'),
                            'Save as QuakeML File', self._saveCatalogDlg)
        fileMenu.addAction(QtGui.QIcon().fromTheme('document-open'),
                            'Load QuakeML File', self._openCatalogDlg)
        fileMenu.addSeparator()
        fileMenu.addAction('Save Plot', self._savePlotDlg)
        fileMenu.addSeparator()
        fileMenu.addAction(QtGui.QIcon().fromTheme('application-exit'),
                            'Exit', self.close)
        aboutMenu = menubar.addMenu('&About')
        aboutMenu.addAction(QtGui.QIcon().fromTheme('info'),
                            'Info', self._infoDlg)

    def _drawFig(self):
        '''
        Draws all matplotlib figures
        '''
        num_plots = len(self._current_st)
        self.fig.clear()
        self._appFilter(draw=False)
        for _i, tr in enumerate(self._current_st):
            self.ax = self.fig.add_subplot(num_plots, 1, _i, yticklabels=[])
            self.ax.plot(tr.data, 'k')
            self.ax.set_xlim([0, tr.data.size])
            self.ax.text(.925, .9, self._current_st[_i].stats.channel,
                            transform=self.ax.transAxes, va='top', ma='left')
            self.ax.channel = tr.stats.channel
        # plot picks
        self._drawPicks(draw=False)
        self.fig.suptitle('%s - %s - %s' % (self._current_st[-1].stats.network,
                            self._current_st[-1].stats.station,
                            self._current_st[-1].stats.starttime.isoformat()),
                            x=.2)
        self._updateSB()
        self.fig.canvas.draw()
        self.canvas.setFocus()

    def _initStations(self):
        '''
        Creates a list holding unique station names
        '''
        self._stations = []
        for _tr in self.st:
            if _tr.stats.station not in self._stations:
                self._stations.append(_tr.stats.station)

    def _getPhases(self):
        '''
        Creates a list holding unique phase names
        '''
        phases = []
        for _pick in self.picks:
            if _pick.phase_hint not in phases:
                phases.append(_pick.phase_hint)
        return phases

    def _streamStation(self, station):
        '''
        Copies the current stream object from self.st through
        obspy.stream.select(station=)
        '''
        if station not in self._stations:
            return
        self._current_stname = station
        self._current_st = self.st.select(station=station).copy()
        # Sort and detrend streams
        self._current_st.sort(['channel'])
        self._current_st.detrend('linear')

    def _setPick(self, xdata, phase, channel, onset=None):
        '''
        Write obspy.core.event.Pick into self.picks list
        '''
        picktime = self._current_st[0].stats.starttime +\
                (xdata * self._current_st[0].stats.delta)
        # Overwrite existing phase's picktime
        for _pick in self._getPicks():
            if _pick.phase_hint == phase:
                _pick.time = picktime
                return

        creation_info = event.CreationInfo(
            author='ObsPy.Stream.pick()',
            creation_time=UTCDateTime())
        # Create new event.Pick()
        this_pick = event.Pick()
        this_pick.time = picktime
        this_pick.phase_hint = phase
        this_pick.waveform_id = event.WaveformStreamID(
            network_code=self._current_st[0].stats.network,
            station_code=self._current_st[0].stats.station,
            location_code=self._current_st[0].stats.location,
            channel_code=channel)
        this_pick.evaluation_mode = 'manual'
        this_pick.creation_info = creation_info
        if onset is not None:
            this_pick.onset = onset
        if self._current_filter is not None:
            this_pick.comments.append(event.Comment(
                        text=str(self.bpfilter[self.fltrcb.currentIndex()])))
        self.picks.append(this_pick)

    def _getPicks(self):
        '''
        Create a list of picks for the current plot
        '''
        this_st_picks = []
        for _i, pick in enumerate(self.picks):
            if pick.waveform_id.station_code == self._current_stname and\
                    self._current_st[0].stats.starttime <\
                    pick.time < self._current_st[0].stats.endtime:
                this_st_picks.append(_i)
        return [self.picks[i] for i in this_st_picks]

    def _getPickXPosition(self, picks):
        '''
        Convert picktimes into relative positions along x-axis
        '''
        xpicks = []
        for _pick in picks:
            xpicks.append((_pick.time-self._current_st[0].stats.starttime)
                            / self._current_st[0].stats.delta)
        return np.array(xpicks)

    def _drawPicks(self, draw=True):
        '''
        Draw picklines onto axes
        '''
        picks = self._getPicks()
        xpicks = self._getPickXPosition(picks)

        for _ax in self.fig.get_axes():
            lines = []
            labels = []
            for _i, _xpick in enumerate(xpicks):
                if picks[_i].phase_hint == 'S':
                    color = 'r'
                elif picks[_i].phase_hint == 'P':
                    color = 'g'
                else:
                    color = 'b'
                lines.append(matplotlib.lines.Line2D([_xpick, _xpick],
                            [_ax.get_ylim()[0]*.9, _ax.get_ylim()[1]*.8],
                            color=color))
                labels.append(matplotlib.text.Text(_xpick+20,
                            _ax.get_ylim()[0]*.8, text=picks[_i].phase_hint,
                            color=color, size=10))

            # delete all artists
            del _ax.artists[0:]
            # add updated objects
            for line in lines:
                _ax.add_artist(line)
            for label in labels:
                _ax.add_artist(label)

        if draw:
            self.fig.canvas.draw()
            self.fig.canvas.setFocus()

    # Plot Controls
    def _pltOnScroll(self, event):
        if event.inaxes is None:
            return

        if event.key == 'control':
            axes = self.fig.get_axes()
        else:
            axes = [event.inaxes]

        for _ax in axes:
            left = _ax.get_xlim()[0]
            right = _ax.get_xlim()[1]
            extent = right - left
            dzoom = .15 * extent
            aspect_left = (event.xdata - _ax.get_xlim()[0]) / extent
            aspect_right = (_ax.get_xlim()[1] - event.xdata) / extent

            if event.button == 'up':
                left += dzoom * aspect_left
                right -= dzoom * aspect_right
            elif event.button == 'down':
                left -= dzoom * aspect_left
                right += dzoom * aspect_right
            else:
                return
            _ax.set_xlim([left, right])
        self.fig.canvas.draw()

    def _pltOnDrag(self, event):
        '''
        Redraws the plot upon drag
        '''
        if event.inaxes is None:
            return

        if event.key == 'control':
            axes = self.fig.get_axes()
        else:
            axes = [event.inaxes]

        if event.button == 2:
            if self._plt_drag is None:
                self._plt_drag = event.xdata
                return
            for _ax in axes:
                _ax.set_xlim([_ax.get_xlim()[0] +
                        (self._plt_drag - event.xdata),
                        _ax.get_xlim()[1] + (self._plt_drag - event.xdata)])
        else:
            return
        self.fig.canvas.draw()

    def _pltOnButtonRelease(self, event):
        self._plt_drag = None

    def _pltOnButtonPress(self, event):
        if event.key is not None:
            event.key = event.key.lower()
        if event.inaxes is None:
            return

        channel =  event.inaxes.channel
        if event.key == 'q' and event.button == 1:
            self._setPick(event.xdata, 'P', channel)
        elif event.key == 'w' and event.button == 1:
            self._setPick(event.xdata, 'S', channel)
        elif event.key == 'e' and event.button == 1:
            text, ok = QtGui.QInputDialog.getItem(self, 'Custom Phase',
                'Enter phase name:', self._getPhases())
            if ok:
                self._setPick(event.xdata, text, channel)
        else:
            return
        self._updateSB()
        self._drawPicks()

    def _pltNextStation(self):
        '''
        Plot next station
        '''
        self._streamStation(self._stationCycle.next())
        self._drawFig()

    def _pltPrevStation(self):
        '''
        Plot previous station
        '''
        for _i in range(len(self._stations)-1):
            prevStation = self._stationCycle.next()
        self._streamStation(prevStation)
        self._drawFig()

    def _pltStation(self):
        '''
        Plot station from DropDown Menu
        '''
        self._streamStation(self._stations[self.stcb.currentIndex()])
        self._drawFig()

    # Filter functions
    def _appFilter(self, button=True, draw=True):
        '''
        Apply filter
        '''
        _i = self.fltrcb.currentIndex()
        self._streamStation(self._current_stname)
        if self.fltrbtn.isChecked() is False:
            self._current_filter = None
        else:
            self._current_st.filter('bandpass',
                                    freqmin=self.bpfilter[_i]['freqmin'],
                                    freqmax=self.bpfilter[_i]['freqmax'],
                                    corners=self.bpfilter[_i]['corners'],
                                    zerophase=True)
            self._current_filter = _i
        for _i, _ax in enumerate(self.fig.get_axes()):
            if len(_ax.lines) == 0:
                continue
            _ax.lines[0].set_ydata(self._current_st[_i].data)
            _ax.relim()
            _ax.autoscale_view()
        if draw is True:
            self._drawPicks(draw=False)
            self.fig.canvas.draw()
            self.canvas.setFocus()
        self._updateSB()

    def _newFilter(self):
        '''
        Create new filter
        '''
        newFilter = self.defFilter(self)
        if newFilter.exec_():
                self.bpfilter.append(newFilter.getValues())
                self._updateFilterCB()
                self.fltrcb.setCurrentIndex(len(self.bpfilter)-1)
                self._appFilter()

    def _editFilter(self):
        '''
        Edit existing filter
        '''
        _i = self.fltrcb.currentIndex()
        this_filter = self.bpfilter[_i]
        editFilter = self.defFilter(self, this_filter)
        if editFilter.exec_():
                self.bpfilter[_i] = editFilter.getValues()
                self._updateFilterCB()
                self.fltrcb.setCurrentIndex(_i)
                self._appFilter()

    def _deleteFilter(self):
        '''
        Delete filter
        '''
        _i = self.fltrcb.currentIndex()
        self.fltrbtn.setChecked(False)
        self.bpfilter.pop(_i)
        self._updateFilterCB()
        self._appFilter()

    def _changeFilter(self, index):
        '''
        Evoke this is filter in drop-down is changed
        '''
        if index == len(self.bpfilter):
            return self._newFilter()
        else:
            return self._appFilter()

    def _updateFilterCB(self):
        '''
        Update the filter QComboBox
        '''
        self.fltrcb.clear()
        self.fltrcb.setCurrentIndex(-1)
        for _i, _f in enumerate(self.bpfilter):
            self.fltrcb.addItem('%s [%.2f - %.2f Hz]' % (_f['name'],
                _f['freqmin'], _f['freqmax']))
        self.fltrcb.addItem('Create new Filter...')

    # Status bar functions
    def _createStatusBar(self):
        '''
        Creates the status bar
        '''
        sb = QtGui.QStatusBar()
        sb.setFixedHeight(18)
        self.setStatusBar(sb)
        self.statusBar().showMessage('Ready')

    def _updateSB(self, statustext=None):
        '''
        Updates the statusbar text
        '''
        if statustext is None:
            self.stcb.setCurrentIndex(
                self._stations.index(self._current_stname))
            msg = 'Station %i/%i - %i Picks' % (
                self._stations.index(self._current_stname)+1,
                len(self._stations), len(self._getPicks()))
            if self._current_filter is not None:
                msg += ' - Bandpass %s [%.2f - %.2f Hz]' % (
                    self.bpfilter[self._current_filter]['name'],
                    self.bpfilter[self._current_filter]['freqmin'],
                    self.bpfilter[self._current_filter]['freqmax'])
            else:
                msg += ' - Raw Data'
            self.statusBar().showMessage(msg)

    def _openCatalogDlg(self):
        filename = QtGui.QFileDialog.getOpenFileName(self,
                        'Load QuakeML Picks',
                        os.getcwd(), 'QuakeML Format (*.xml)', '20')
        if filename:
            self._openCatalog(str(filename))

    def _openCatalog(self, filename):
        try:
            cat = event.readEvents(filename)
            self.picks = cat[0].picks
            self._drawPicks()
        except:
            msg = 'Could not open QuakeML file %s' % (filename)
            raise IOError(msg)

    def _saveCatalogDlg(self):
        self.savefile = QtGui.QFileDialog.getSaveFileName(self,
                        'Save QuakeML Picks',
                        os.getcwd(), 'QuakeML Format (*.xml)')
        if not self.savefile:
            self.savefile = None
            return
        self.savefile = str(self.savefile)
        if os.path.splitext(self.savefile)[1].lower() != '.xml':
            self.savefile += '.xml'
        self._saveCatalog()

    def _saveCatalog(self, filename=None):
        if self.savefile is None and filename is None:
            return self._saveCatalogDlg()
        if filename is not None:
            self.savefile = filename
        cat = event.Catalog()
        cat.events.append(event.Event(picks=self.picks))
        cat.write(self.savefile, format='QUAKEML')

    def _savePlotDlg(self):
        filename = QtGui.QFileDialog.getSaveFileName(self, 'Save Plot',
                        os.getcwd(),
                        'Image Format (*.png *.pdf *.ps *.svg *.eps)')
        if not filename:
            return
        filename = str(filename)
        format = os.path.splitext(filename)[1][1:].lower()
        if format not in ['png', 'pdf', 'ps' , 'svg',  'eps']:
            format = 'png'
            filename += '.' + format
        self.fig.savefig(filename=filename, format=format)

    def _infoDlg(self):
        msg = """
                <h3><b>obspy.core.stream-Picker</b></h3>
                <br><br>
                This tool is ment to be a lightweight picker for seismological
                wave time picking.<br>
                See <a href=http://www.obspy.org>http://www.obspy.org</a>
                for further documentation.
                <h4>Controls:</h4>
                <blockquote>
                <table>
                    <tr>
                        <td width=20><b>s</b></td><td>Previous stream</td>
                    </tr>
                    <tr>
                        <td width=20><b>d</b></td><td>Next stream</td>
                    </tr>
                    <tr>
                        <td width=20><b>q</b></td>
                        <td>Set S-Phase pick at mouse position</td>
                    </tr>
                    <tr>
                        <td width=20><b>w</b></td>
                        <td>Set P-Phase pick at mouse position</td>
                    </tr>
                    <tr>
                        <td width=20><b>e</b></td>
                        <td>Set custom phase pick at mouse position</td>
                    </tr>
                </table>
                </blockquote>
                <h4>Plot Controls:</h4>
                <blockquote>
                Use mouse wheel to zoom in- and out. Middle mouse button moves
                plot on x-axis.<br>
                Hit <b>Ctrl</b> to manipulate all streams simultaniously.
                </blockquote>
                <br><br>
                Programm stores filter parameters in <code>.pick_filter</code>
                and a backup of recent picks in
                <code>.picks-obspy.xml.bak</code>.
                """
        QtGui.QMessageBox.about(self, 'About', msg)

    def closeEvent(self, evnt):
        '''
        This function is called upon closing the QtGui
        '''
        # Save Picks
        pickle.dump(self.bpfilter, open('.pick_filters', 'w'))
        # Save Catalog
        self._saveCatalog('.picks-obspy.xml.bak')

    # Filter Dialog
    class defFilter(QtGui.QDialog):
        def __init__(self, parent=None, filtervalues=None):
            QtGui.QDialog.__init__(self, parent)
            self.setWindowTitle('Create new Bandpass-Filter')

            # Frequency QDoubleSpinBoxes
            self.frqmin = QtGui.QDoubleSpinBox(decimals=2, maximum=100,
                            minimum=0.01, singleStep=0.1, value=0.1)
            self.frqmax = QtGui.QDoubleSpinBox(decimals=2, maximum=100,
                            minimum=0.01, singleStep=0.1, value=10.0)

            # Radio buttons for corners
            _corners = [2, 4, 8]
            _radbtn = []
            for _c in _corners:
                _radbtn.append(QtGui.QRadioButton(str(_c)))
                if _c == 4:
                    _radbtn[-1].setChecked(True)

            self.corner = QtGui.QButtonGroup()
            self.corner.setExclusive(True)

            radiogrp = QtGui.QHBoxLayout()
            for _i, _r in enumerate(_radbtn):
                self.corner.addButton(_r, _corners[_i])
                radiogrp.addWidget(_radbtn[_i])

            # Filter name
            self.fltname = QtGui.QLineEdit('Filter Name')
            self.fltname.selectAll()

            # Make Layout
            grid = QtGui.QGridLayout()
            grid.addWidget(QtGui.QLabel('Filter Name'), 0, 0)
            grid.addWidget(self.fltname, 0, 1)
            grid.addWidget(QtGui.QLabel('Min. Frequency'), 1, 0)
            grid.addWidget(self.frqmin, 1, 1)
            grid.addWidget(QtGui.QLabel('Max. Frequency'), 2, 0)
            grid.addWidget(self.frqmax, 2, 1)
            grid.addWidget(QtGui.QLabel('Corners'), 3, 0)
            grid.addLayout(radiogrp, 3, 1)
            grid.setVerticalSpacing(10)

            btnbox = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok |
                                            QtGui.QDialogButtonBox.Cancel)
            btnbox.accepted.connect(self.accept)
            btnbox.rejected.connect(self.reject)

            layout = QtGui.QVBoxLayout()
            layout.addWidget(QtGui.QLabel('Define a minimum and maximum' +
                ' frequency\nfor the bandpass filter.\nFunction utilises ' +
                'obspy.signal.filter (zerophase=True).\n'))
            layout.addLayout(grid)
            layout.addWidget(btnbox)

            if filtervalues is not None:
                self.fltname.setText(filtervalues['name'])
                self.frqmin.setValue(filtervalues['freqmin'])
                self.frqmax.setValue(filtervalues['freqmax'])
                self.corner.button(filtervalues['corners']).setChecked(True)

            self.setLayout(layout)
            self.setSizeGripEnabled(False)

        def getValues(self):
            '''
            Return filter dialogs values as a dictionary
            '''
            return dict(name=str(self.fltname.text()),
                        freqmin=float(self.frqmin.cleanText()),
                        freqmax=float(self.frqmax.cleanText()),
                        corners=int(int(self.corner.checkedId())))



st = read('../OKAS01/*.mseed')
for tr in st:
    tr.trim(starttime=tr.stats.starttime, endtime=tr.stats.starttime+60)
new_pick = streamPick(stream=st)
print new_pick.picks