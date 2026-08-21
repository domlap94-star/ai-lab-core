#r "../bin/tests/Recovery.Tests.dll"
if (Args.Count != 1) throw new System.Exception("package argument required");
System.Console.WriteLine("RECOVERY_HELPERS_VERIFIED=" + TestRunner.VerifyPackage(Args[0]));
