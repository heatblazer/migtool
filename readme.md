SVN to GIT migration tool
======

- merges svn manual commit to git and adds meta info as a revision number
- tags git commits with adequate tags taken from svn ABM commits
- does BFG to clean up repo history from binary
- updates platforms xml with desired commit hashes based on a tagged repo
- and much more ... :) 

NOTES:
======
- See eml.json for email registration of a new user
- See mergeoutput.txt for example output of the script
- See the svngitmigration.txt for example input file

WARN:
======
- Do not modify "db.json" file, it's automatic generated and used by the script for meta info (serialization)

TODO:
======
- Use manual command example: git commit --allow-empty --author="yyordanov <yordan.yordanov@verint.com>" -m "Deleted binaries which are moved to nexus [cr: SStoykov] svn-revision:263262" --date=2019-08-19 when SVN not in GIT

author: ilyan.zapryanov@verint.com