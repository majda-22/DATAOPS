# Local Delta smoke test

From the project directory, with the virtual environment activated:

```powershell
python .\scripts\delta_smoke_test.py
```

The script resolves JARs directly from Maven Central using `ivysettings.xml`.
Its isolated `.spark-ivy/maven-central/` cache avoids stale local Maven metadata
that previously selected missing Snappy and Commons Logging artifacts.
The first execution requires internet access; subsequent executions reuse the cache.

On Windows, set `HADOOP_HOME` to a Hadoop installation containing
`bin/winutils.exe` and `bin/hadoop.dll`, and expose the DLL directory on `PATH`.
The script also accepts a project-local installation at
`.tools/hadoop/hadoop-3.4.2/` and adds its `bin` directory to the process PATH.
These settings affect only the script and its child processes.

The local installation used during debugging came from the third-party release:
https://github.com/zehelh/winutils/releases/tag/hadoop-3.4.2
Its build metadata identifies Apache Hadoop source ref `rel/release-3.4.2`.
Apache documents the Windows native-library requirement here:
https://cwiki.apache.org/confluence/display/HADOOP2/WindowsProblems

Downloaded binaries and JAR caches are ignored by Git. A fresh checkout must
provide Windows Hadoop binaries separately. The test recreates only its dedicated
`data/delta_smoke/orders` table and verifies partition overwrite and version-0 reads.
