SVN to GIT migration tool
======

- merges svn manual commit to git and adds meta info as a revision number
- tags git commits with adequate tags taken from svn ABM commits
- does BFG to clean up repo history from binary
- updates platforms xml with desired commit hashes based on a tagged repo
- and much more ... :) 
- db.json format is as: 
  <code>{
      RepoName: 
         {
          "svnrev" : 9999,
          "tags : [1,2,3,4]
         }
  }</code>
- <code>sgutil.py --help </code> to see the full options, or browse the <code>Globals.py</code> for full options

<mark>NOTES:</mark>

- See eml.json for email registration of a new user
- See mergeoutput.txt for example output of the script
- See the svngitmigration.txt for example input file

<mark>WARN:</mark>

- Do not modify "db.json" file, it's automatic generated and used by the script for meta info (serialization)
- if you want to reset the "db.json" entry, set the "svnrev" to 0

<mark>Missing repos (not present in GIT but requested from svn):</mark>
- Sau 4_5_1 
- SdkBindings 1_0_0 
- Nimbuzz 1_0_0
- Infra 1_1_0
- SdkBindings 1_0_0
- Edr 1_0_0
- FacebookMail
- AccessUrl 1_0_0
- HttpAggregation 1_0_0, 1_0_1, 1_0_3, 1_0_4
- Rainbow 1_0_0

<mark>TODO:</mark>

- Use manual command example: <code>git commit --allow-empty --author="yyordanov <yordan.yordanov@verint.com>" -m "Deleted binaries which are moved to nexus [cr: SStoykov] svn-revision:263262" --date=2019-08-19</code> when SVN not in GIT
- Review the Platforms.git 4_5_3 to verify if commits have to be removed and re-merged. Temporaly removed http://tlvsvn1/svn/repos-pdfe/Pdfe/Platforms/branches/4_5_3,https://cisbitbucket01/projects/IP/Platforms.git,4_5_3 the link from the file
  
author: iliyan.zapryanov@verint.com