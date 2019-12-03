#Globals and constants
############################################################################
class NS:
    class Errors: #enum like
        OK = 0
        ERROR = 1
        NO_CONNECTION_TO_SVN = 2
        NO_CONNECTION_TO_GIT = 3
        ERROR_INSUFFICIENT_CLONE_DEPTH = 4


    TEST_GIT_REPO_NAME = None #"TST4" #"TODO_MIGRATE"

    EXPLICIT_MATCH = "Sau_4_5_3"

    GDEBUG = False

    BFORCE_ALL = False #MUST BE False in Release!!!

    REPO_BACKUP = "backup"

    GUserMails = None

    GMissingMails = {}

    GSvnGitMeta = []

    GSwitchCase = {}

    SVNGIT_UPDATE_DB_ONLY = False

    SVNGIT_ON_ABM = False

    GDepth = 20

    CMD_VERBOSE_MODE_ON = True

    CSI_GIT_URI = "ssh://git@cisbitbucket01:7999/"

    SVN_TEMP_DIR = "svnrepos"

    GIT_TEMP_DIR = "gitrepos"

    ABM_TEMP = "abmtemp"

    LOG_DISABLED = True

    GTHREAD_COUNT = 5 #test

    FIX_DIRTY_TAGS = False

    FIX_DIRTY_TAGS_SPECIAL = False

    HELP_MESSAGE = """

    Usage:\r\n
    For bfg mode to perform a cleanup use: sgutil.py --bfg --file <file>\r\n
    For merge export svn to git use: sgutil.py --export --file <file>\r\n
    For tagging use: sgutil.py --file <file> --tag <0, 1, 2>\r\n
        \t(desc: where 0 is tag, 1 is untag, and 2 is retag (untag, tag) )\r\n
    For untagging use: sgutil.py --file <file> --untag\r\n
    For dump log use: sgutil.py --file <file> --dump-all\r\n
    For complete merge repo and tag use: sgutil.py --file <file> --fullmerge\r\n
    For specific removal of tags use: sgutil.py --file <file> --purge-tags\r\n
    For other options view the sgutil.py file with your editor of choice :")\r\n
    For updating a db file use: sgutil.py --update-db\r\n
    For hinting you are on a build machine use: sgutil.py --abm\r\n
    Usage for updateing ComponentsVersion.xml:\r\n
    -cv0 <filename.xml> ... -cv<Filename.xml>\r\n
    ----------------------------------------------------------------------------\r\n
    """

    ExcludedFilesForGitV1 = """
    7z,arj,deb,pkg,rar,rpm,tar,
    gz,tar.gz,z,ace,whl,gzip,zip,
    bin,dmg,iso,toast,vcd,dat,db,apk,
    exe,jar,war,ear,cab,dll,obj,dmp,
    xlsx,docx,doc,ppt,pptm,pptx,
    pdf,msi,msu,m_s_i,wsi,png,
    jpg,jpeg,gif,ico
    """

    ExcludedFilesForGitV2 = """
    .cache,.chm,.dll,.exe,
    .exp,.idb,.jpg,.lib,.Lib,
    .ncb,.pcap,.pdf,.pk,.raw,
    .obj,.pdb,.sdf,.suo,
    .d,.Config.proj.bak,
    .docx,.xlsx,.snoop,.AIT,
    .o,.so,.out,.metadata
    """

    Gargs = {}
    Gargs.update({'--option' : None})
    Gargs.update({'--bfg':None})    
    Gargs.update({'--file':None})
    Gargs.update({'--merge':None})
    Gargs.update({'--clean':None})
    Gargs.update({'--optimize':None})
    Gargs.update({'--help' : HELP_MESSAGE})    
    Gargs.update({'--nolog':None})
    Gargs.update({'--tag' : None})
    Gargs.update({'--retag' : None})
    Gargs.update({'--untag' : None})
    Gargs.update({'--xml-file' : None})
    Gargs.update({'--fix-dirty' : None})
    Gargs.update({'--export-platforms' : None})
    Gargs.update({'--fullmerge' : None})
    Gargs.update({'--dump-all' : None})
    Gargs.update({'--purge-tags' : None})
    Gargs.update({'--update-db' : None})
    Gargs.update({'--abm' : None})
    Gargs.update({'--force' : None})
    Gargs.update({'--explicit' : None})
    


#######################################################################################################################################
#bdata section (put binary or RO data below) w/marker tag