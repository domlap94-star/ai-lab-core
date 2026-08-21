#r "../bin/tests/Recovery.Tests.dll"
var code = TestRunner.RunAll();
if (code != 0) throw new System.Exception("recovery_unit_tests_failed");
