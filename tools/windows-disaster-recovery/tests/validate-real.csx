#r "../bin/tests/Recovery.Tests.dll"
if (Args.Count != 1) throw new System.Exception("checkpoint argument required");
System.Console.WriteLine(TestRunner.ValidateCheckpoint(Args[0]));
