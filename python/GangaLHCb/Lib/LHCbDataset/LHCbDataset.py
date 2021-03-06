#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#

from copy import deepcopy
import tempfile
import fnmatch
from Ganga.GPIDev.Lib.Dataset import GangaDataset
from Ganga.GPIDev.Schema import GangaFileItem, SimpleItem, Schema, Version
from Ganga.GPIDev.Base import GangaObject
from Ganga.Utility.Config import getConfig, ConfigError
import Ganga.Utility.logging
from LHCbDatasetUtils import isLFN, isPFN, isDiracFile, strToDataFile, getDataFile
from OutputData import OutputData
from Ganga.GPIDev.Base.Proxy import isType, stripProxy, GPIProxyObjectFactory
from Ganga.GPIDev.Lib.Job.Job import Job, JobTemplate
from GangaDirac.Lib.Backends.DiracUtils import get_result
from Ganga.GPIDev.Lib.GangaList.GangaList import GangaList, makeGangaListByRef
from Ganga.GPIDev.Lib.File import IGangaFile
## Can't do due to circular problems
#from Ganga.GPI import DiracFile
logger = Ganga.Utility.logging.getLogger()

#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#


class LHCbDataset(GangaDataset):

    '''Class for handling LHCb data sets (i.e. inputdata for LHCb jobs).

    Example Usage:
    ds = LHCbDataset(["lfn:/some/lfn.file","pfn:/some/pfn.file"])
    ds[0] # DiracFile("/some/lfn.file") - see DiracFile docs for usage
    ds[1] # PhysicalFile("/some/pfn.file")- see PhysicalFile docs for usage
    len(ds) # 2 (number of files)
    ds.getReplicas() # returns replicas for *all* files in the data set
    ds.replicate("CERN-USER") # replicate *all* LFNs to "CERN-USER" SE
    ds.getCatalog() # returns XML catalog slice
    ds.optionsString() # returns Gaudi-sytle options 
    [...etc...]
    '''
    schema = {}
    docstr = 'List of PhysicalFile and DiracFile objects'
    schema['files'] = GangaFileItem(defvalue=[], typelist=[
                                    'str', 'Ganga.GPIDev.Lib.File.IGangaFile.IGangaFile'], sequence=1, doc=docstr)
    docstr = 'Ancestor depth to be queried from the Bookkeeping'
    schema['depth'] = SimpleItem(defvalue=0, doc=docstr)
    docstr = 'Use contents of file rather than generating catalog.'
    schema['XMLCatalogueSlice'] = GangaFileItem(defvalue=None, doc=docstr)
    docstr = 'Specify the dataset persistency technology'
    schema['persistency'] = SimpleItem(
        defvalue=None, typelist=['str', 'type(None)'], doc=docstr)

    _schema = Schema(Version(3, 0), schema)
    _category = 'datasets'
    _name = "LHCbDataset"
    _exportmethods = ['getReplicas', '__len__', '__getitem__', 'replicate',
                      'hasLFNs', 'append', 'extend', 'getCatalog', 'optionsString',
                      'getLFNs', 'getFileNames', 'getFullFileNames',
                      'difference', 'isSubset', 'isSuperset', 'intersection',
                      'symmetricDifference', 'union', 'bkMetadata',
                      'isEmpty', 'hasPFNs', 'getPFNs']  # ,'pop']

    def __init__(self, files=[], persistency=None, depth=0):
        new_files = GangaList()
        if isType(files, LHCbDataset):
            for this_file in files:
                new_files.append(copy.deepcopy(this_file))
        elif isType(files, IGangaFile):
            new_files.append(copy.deepcopy(this_file))
        elif type(files) == type([]):
            for this_file in files:
                if type(this_file) == type(''):
                    new_files.append(string_datafile_shortcut_lhcb(this_file, None), False)
                elif isType(this_file, IGangaFile):
                    new_files.append(this_file, False)
                else:
                    new_files.append(strToDataFile(this_file))
        elif type(files) == type(''):
            new_files.append(string_datafile_shortcut_lhcb(this_file, None), False)
        else:
            from Ganga.Core.exceptions import GangaException
            raise GangaException("Unknown object passed to LHCbDataset constructor!")
        new_files._setParent(self)
        super(LHCbDataset, self).__init__()
        # Feel free to turn this on again for debugging but it's potentially quite expensive
        #logger.debug( "Creating dataset with:\n%s" % files )
        self.files = new_files
        self.persistency = persistency
        self.depth = depth
        logger.debug("Dataset Created")

    def __deepcopy__(self, memo):
        cls = type(stripProxy(self))
        obj = super(cls, cls).__new__(cls)
        dict = stripProxy(self).__getstate__()
        for n in dict:
            dict[n] = deepcopy(dict[n], memo)
            if n == 'files':
                for file in dict['files']:
                    stripProxy(file)._setParent(obj)
        obj.__setstate__(dict)
        return obj

    def __construct__(self, args):
        logger.debug("__construct__")
        self.files = []
        if (len(args) != 1):
            super(LHCbDataset, self).__construct__(args[1:])

        logger.debug("__construct__: %s" % str(args))

        if len(args) == 0:
            return

        self.files = []
        if type(args[0]) == type(''):
            this_file = string_datafile_shortcut_lhcb(args[0], None)
            self.files.append(file_arg)
        else:
            for file_arg in args[0]:
                if type(file_arg) is type(''):
                    this_file = string_datafile_shortcut_lhcb(file_arg, None)
                else:
                    this_file = file_arg
                self.files.append(file_arg)
        # Equally as expensive
        #logger.debug( "Constructing dataset len: %s\n%s" % (str(len(self.files)), str(self.files) ) )
        logger.debug("Constructing dataset len: %s" % str(len(self.files)))

    def __len__(self):
        """The number of files in the dataset."""
        result = 0
        if self.files:
            result = len(self.files)
        return result

    def __nonzero__(self):
        """This is always True, as with an object."""
        return True

    def __getitem__(self, i):
        '''Proivdes scripting (e.g. ds[2] returns the 3rd file) '''
        #this_file = self.files[i]
        # print type(this_file)
        # return this_file
        # return GPIProxyObjectFactory(this_file)
        # return this_file
        if type(i) == type(slice(0)):
            ds = LHCbDataset(files=self.files[i])
            ds.depth = self.depth
            #ds.XMLCatalogueSlice = self.XMLCatalogueSlice
            return GPIProxyObjectFactory(ds)
        else:
            return GPIProxyObjectFactory(self.files[i])

    def isEmpty(self): return not bool(self.files)

    def getReplicas(self):
        'Returns the replicas for all files in the dataset.'
        lfns = self.getLFNs()
        cmd = 'getReplicas(%s)' % str(lfns)
        result = get_result(cmd, 'LFC query error', 'Could not get replicas.')
        return result['Value']['Successful']

    def hasLFNs(self):
        'Returns True is the dataset has LFNs and False otherwise.'
        for f in self.files:
            if isDiracFile(GPIProxyObjectFactory(f)):
                return True
        return False

    def hasPFNs(self):
        'Returns True is the dataset has PFNs and False otherwise.'
        for f in self.files:
            if not isDiracFile(GPIProxyObjectFactory(f)):
                return True
        return False

    def replicate(self, destSE='', srcSE='', locCache=''):
        '''Replicate all LFNs to destSE.  For a list of valid SE\'s, type
        ds.replicate().'''
        if not destSE:
            from Ganga.GPI import DiracFile
            DiracFile().replicate('')
            return
        if not self.hasLFNs():
            raise GangaException('Cannot replicate dataset w/ no LFNs.')
        retry_files = []
        for f in self.files:
            if not isDiracFile(GPIProxyObjectFactory(f)):
                continue
            try:
                result = f.replicate(destSE, srcSE, locCache)
            except:
                msg = 'Replication error for file %s (will retry in a bit).'\
                      % f.lfn
                logger.warning(msg)
                retry_files.append(f)
        for f in retry_files:
            try:
                result = f.replicate(destSE, srcSE, locCache)
            except:
                msg = '2nd replication attempt failed for file %s.' \
                      ' (will not retry)' % f.lfn
                logger.warning(msg)
                logger.warning(str(result))

    def append(self, input_file):
        self.extend([input_file])

    def extend(self, files, unique=False):
        '''Extend the dataset. If unique, then only add files which are not
        already in the dataset.'''
        from Ganga.GPIDev.Base import ReadOnlyObjectError

        if self._parent is not None and self._parent._readonly():
            raise ReadOnlyObjectError('object Job#%s  is read-only and attribute "%s/inputdata" cannot be modified now' % (self._parent.id, self._name))

        _external_files = []

        if type(files) == type('') or isType(files, IGangaFile):
            _external_files = [files]
        elif type(files) == type([]):
            _external_files = files
        elif isType(files, LHCbDataset):
            _external_files = files.files
        else:
            if not hasattr(files, "__getitem__") or not hasattr(files, '__iter__'):
                _external_files = [files]

        # just in case they extend w/ self
        _to_remove = []
        for this_file in _external_files:
            if hasattr(this_file, 'subfiles'):
                if len(this_file.subfiles) > 0:
                    _external_files = makeGangaListByRef(this_file.subfiles)
                    _to_remove.append(this_file)
            if type(this_file) == type(''):
                _external_files.append(string_datafile_shortcut_lhcb(this_file, None))
                _to_remove.append(this_file)

        for _this_file in _to_remove:
            _external_files.pop(_external_files.index(_this_file))

        for this_f in _external_files:
            _file = getDataFile(this_f)
            if _file is None:
                _file = this_f
            myName = _file.namePattern
            from Ganga.GPI import DiracFile
            if isType(_file, DiracFile):
                myName = _file.lfn
            if unique and myName in self.getFileNames():
                continue
            self.files.append(_file)

    def removeFile(self, file):
        try:
            self.files.remove(file)
        except:
            raise GangaException('Dataset has no file named %s' % file.name)

    def getLFNs(self):
        'Returns a list of all LFNs (by name) stored in the dataset.'
        lfns = []
        if not self:
            return lfns
        for f in self.files:
            if isDiracFile(GPIProxyObjectFactory(f)):
                subfiles = f.getSubFiles()
                if len(subfiles) == 0:
                    lfns.append(f.lfn)
                else:
                    for file in subfiles:
                        lfns.append(file.lfn)

        #logger.debug( "Returning LFNS:\n%s" % str(lfns) )
        logger.debug("Returning #%s LFNS" % str(len(lfns)))
        return lfns

    def getPFNs(self):
        'Returns a list of all PFNs (by name) stored in the dataset.'
        pfns = []
        if not self:
            return pfns
        for f in self.files:
            if isPFN(f):
                pfns.append(f.namePattern)
        return pfns

    def getFileNames(self):
        'Returns a list of the names of all files stored in the dataset.'
        names = []
        from Ganga.GPI import DiracFile
        for i in self.files:
            if isType(i, DiracFile):
                names.append(i.lfn)
            else:
                try:
                    names.append(i.namePattern)
                except:
                    logger.warning("Cannot determine filename for: %s " % i)
                    raise GangaException("Cannot Get File Name")

        return names

    def getFullFileNames(self):
        'Returns all file names w/ PFN or LFN prepended.'
        names = []
        from Ganga.GPI import DiracFile
        for f in self.files:
            if isType(f, DiracFile):
                names.append('LFN:%s' % f.lfn)
            else:
                try:
                    names.append('PFN:%s' % f.namePattern)
                except:
                    logger.warning("Cannot determine filename for: %s " % i)
                    raise GangaException("Cannot Get File Name")
        return names

    def getCatalog(self, site=''):
        '''Generates an XML catalog from the dataset (returns the XML string).
        Note: site defaults to config.LHCb.LocalSite
        Note: If the XMLCatalogueSlice attribute is set, then it returns
              what is written there.'''
        if hasattr(self.XMLCatalogueSlice, 'name'):
            if self.XMLCatalogueSlice.name:
                f = open(self.XMLCatalogueSlice.name)
                xml_catalog = f.read()
                f.close()
                return xml_catalog
        if not site:
            site = getConfig('LHCb')['LocalSite']
        lfns = self.getLFNs()
        depth = self.depth
        tmp_xml = tempfile.NamedTemporaryFile(suffix='.xml')
        cmd = 'getLHCbInputDataCatalog(%s,%d,"%s","%s")' \
              % (str(lfns), depth, site, tmp_xml.name)
        result = get_result(cmd, 'LFN->PFN error', 'XML catalog error.')
        xml_catalog = tmp_xml.read()
        tmp_xml.close()
        return xml_catalog

    def optionsString(self, file=None):
        'Returns the Gaudi-style options string for the dataset (if a filename' \
            ' is given, the file is created and output is written there).'
        if not self or len(self) == 0:
            return ''
        snew = ''
        if self.persistency == 'ROOT':
            snew = '\n#new method\nfrom GaudiConf import IOExtension\nIOExtension(\"%s\").inputFiles([' % self.persistency
        elif self.persistency == 'POOL':
            snew = '\ntry:\n    #new method\n    from GaudiConf import IOExtension\n    IOExtension(\"%s\").inputFiles([' % self.persistency
        elif self.persistency == None:
            snew = '\ntry:\n    #new method\n    from GaudiConf import IOExtension\n    IOExtension().inputFiles(['
        else:
            logger.warning(
                "Unknown LHCbDataset persistency technology... reverting to None")
            snew = '\ntry:\n    #new method\n    from GaudiConf import IOExtension\n    IOExtension().inputFiles(['

        sold = '\nexcept ImportError:\n    #Use previous method\n    from Gaudi.Configuration import EventSelector\n    EventSelector().Input=['
        sdatasetsnew = ''
        sdatasetsold = ''

        dtype_str_default = getConfig('LHCb')['datatype_string_default']
        dtype_str_patterns = getConfig('LHCb')['datatype_string_patterns']
        for f in self.files:
            dtype_str = dtype_str_default
            for this_str in dtype_str_patterns:
                matched = False
                for pat in dtype_str_patterns[this_str]:
                    if fnmatch.fnmatch(f.namePattern, pat):
                        dtype_str = this_str
                        matched = True
                        break
                if matched:
                    break
            sdatasetsnew += '\n        '
            sdatasetsold += '\n        '
            if isDiracFile(f):
                sdatasetsnew += """ \"LFN:%s\",""" % f.lfn
                sdatasetsold += """ \"DATAFILE='LFN:%s' %s\",""" % (f.lfn, dtype_str)
            else:
                sdatasetsnew += """ \"PFN:%s\",""" % f.namePattern
                sdatasetsold += """ \"DATAFILE='PFN:%s' %s\",""" % (f.namePattern, dtype_str)
        if sdatasetsold.endswith(","):
            if self.persistency == 'ROOT':
                sdatasetsnew = sdatasetsnew[:-1] + """\n], clear=True)"""
            else:
                sdatasetsnew = sdatasetsnew[:-1] + """\n    ], clear=True)"""
            sdatasetsold = sdatasetsold[:-1]
            sdatasetsold += """\n    ]"""
        if(file):
            f = open(file, 'w')
            if self.persistency == 'ROOT':
                f.write(snew)
                f.write(sdatasetsnew)
            else:
                f.write(snew)
                f.write(sdatasetsnew)
                f.write(sold)
                f.write(sdatasetsold)
            f.close()
        else:
            if self.persistency == 'ROOT':
                return snew + sdatasetsnew
            else:
                return snew + sdatasetsnew + sold + sdatasetsold

    def difference(self, other):
        '''Returns a new data set w/ files in this that are not in other.'''
        other_files = other.getFullFileNames()
        files = set(self.getFullFileNames()).difference(other_files)
        data = LHCbDataset()
        data.__construct__([list(files)])
        data.depth = self.depth
        return GPIProxyObjectFactory(data)

    def isSubset(self, other):
        '''Is every file in this data set in other?'''
        return set(self.getFileNames()).issubset(other.getFileNames())

    def isSuperset(self, other):
        '''Is every file in other in this data set?'''
        return set(self.getFileNames()).issuperset(other.getFileNames())

    def symmetricDifference(self, other):
        '''Returns a new data set w/ files in either this or other but not
        both.'''
        other_files = other.getFullFileNames()
        files = set(self.getFullFileNames()).symmetric_difference(other_files)
        data = LHCbDataset()
        data.__construct__([list(files)])
        data.depth = self.depth
        return GPIProxyObjectFactory(data)

    def intersection(self, other):
        '''Returns a new data set w/ files common to this and other.'''
        other_files = other.getFullFileNames()
        files = set(self.getFullFileNames()).intersection(other_files)
        data = LHCbDataset()
        data.__construct__([list(files)])
        data.depth = self.depth
        return GPIProxyObjectFactory(data)

    def union(self, other):
        '''Returns a new data set w/ files from this and other.'''
        files = set(self.getFullFileNames()).union(other.getFullFileNames())
        data = LHCbDataset()
        data.__construct__([list(files)])
        data.depth = self.depth
        return GPIProxyObjectFactory(data)

    def bkMetadata(self):
        'Returns the bookkeeping metadata for all LFNs. '
        logger.info(
            "Using BKQuery(bkpath).getDatasetMetadata() with bkpath=the bookkeeping path, will yeild more metadata such as 'TCK' info...")
        cmd = 'bkMetaData(%s)' % self.getLFNs()
        b = get_result(cmd, 'Error removing replica', 'Replica rm error.')
        return b

    # def pop(self,file):
    #    if type(file) is type(''): file = strToDataFile(file,False)
    #    try: job = self.getJobObject()
    #    except: job = None
    #    if job:
    #        if job.status != 'new' and job.status != 'failed':
    #            msg = 'Cannot pop file b/c the job status is "%s". '\
    #                  'Job must be either "new" or "failed".' % job.status
    #            raise GangaException(msg)
    #        master = job.master
    #        if job.subjobs:
    #            self.removeFile(file)
    #            for sj in job.subjobs:
    #                try: sj.inputdata.removeFile(file)
    #                except: pass
    #        elif master:
    #            master.inputdata.removeFile(file)
    #            self.removeFile(file)
    #        else: self.removeFile(file)
    #    else:
    #        self.removeFile(file)

#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#

from Ganga.GPIDev.Base.Filters import allComponentFilters


def string_datafile_shortcut_lhcb(name, item):

    # Overload the LHCb instance if the Core beet us to it
    mainFileOutput = None
    try:
        mainFileOutput = Ganga.GPIDev.Lib.File.string_file_shortcut(name, item)
    except Exception, x:
        logger.debug("Failed to Construct a default file type: %s" % str(name))
        pass

    #   We can do some 'magic' with strings so lets do that here
    if (mainFileOutput is not None):
        #logger.debug( "Core Found: %s" % str( mainFileOutput ) )
        if (type(name) is not type('')):
            return mainFileOutput

    if type(name) is not type(''):
        return None
    if item is None and name is None:
        return None  # used to be c'tor, but shouldn't happen now
    else:  # something else...require pfn: or lfn:
        try:
            this_file = strToDataFile(name, True)
            if this_file is None:
                if not mainFileOutput is None:
                    return mailFileOutput
                else:
                    raise GangaException("Failed to find filetype for: %s" % str(name))
            return this_file
        except Exception, x:
            # if the Core can make a file object from a string then use that,
            # else raise an error
            if not mainFileOutput is None:
                return mainFileOutput
            else:
                raise x
    return None

allComponentFilters['gangafiles'] = string_datafile_shortcut_lhcb

# Name of this method set in the GPIComponentFilters section of the
# Core... either overload this default or leave it

def string_dataset_shortcut(files, item):
    from GangaLHCb.Lib.Tasks.LHCbTransform import LHCbTransform
    from Ganga.GPIDev.Base.Objects import ObjectMetaclass
    # This clever change mirrors that in IPostprocessor (see there)
    # essentially allows for dynamic extensions to JobTemplate
    # such as LHCbJobTemplate etc.

    inputdataList = [stripProxy(i)._schema.datadict['inputdata'] for i in Ganga.GPI.__dict__.values()
                     if isinstance(stripProxy(i), ObjectMetaclass)
                     and (issubclass(stripProxy(i), Job) or issubclass(stripProxy(i), LHCbTransform))
                     and 'inputdata' in stripProxy(i)._schema.datadict]
    if type(files) is not type([]):
        return None
    if item in inputdataList:
        ds = LHCbDataset()
        ds.__construct__([files])
        return ds
    else:
        return None  # used to be c'tors, but shouldn't happen now

allComponentFilters['datasets'] = string_dataset_shortcut

#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#

