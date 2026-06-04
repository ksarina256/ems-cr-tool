import unittest

from ccgit.runner import CommandError, CommandRunner


class RunnerTest(unittest.TestCase):
    def test_missing_command_can_be_nonfatal(self):
        result = CommandRunner().run(["definitely-not-a-real-command-ccgit"], check=False)

        self.assertEqual(result.returncode, 127)
        self.assertIn("definitely-not-a-real-command-ccgit", result.stderr)

    def test_missing_command_raises_when_checked(self):
        with self.assertRaises(CommandError):
            CommandRunner().run(["definitely-not-a-real-command-ccgit"], check=True)


if __name__ == "__main__":
    unittest.main()
