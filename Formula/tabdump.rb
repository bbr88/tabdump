class Tabdump < Formula
  desc "TabDump CLI and runtime integration for periodic browser tab dumps"
  homepage "https://github.com/bbr88/tabdump"
  license "MIT"

  # Phase 4 bootstrap formula:
  # Replace url/sha256 with the current release artifact + checksum.
  url "https://github.com/bbr88/tabdump/releases/download/v0.0.2-test/tabdump-app-v0.0.2-test.tar.gz"
  sha256 :no_check

  depends_on :macos

  def install
    libexec.install Dir["*"]

    (bin/"tabdump-install").write <<~EOS
      #!/usr/bin/env bash
      set -euo pipefail
      exec "#{libexec}/scripts/install.sh" --app-archive "#{libexec}/tabdump-app-v0.0.2-test.tar.gz" "$@"
    EOS
    chmod 0755, bin/"tabdump-install"
  end

  def caveats
    <<~EOS
      Bootstrap formula only. Replace url/sha256 and archive name per release.

      To complete local runtime install:
        tabdump-install --yes --vault-inbox ~/obsidian/Inbox/
    EOS
  end

  test do
    assert_match "Usage:", shell_output("#{bin}/tabdump-install --help")
  end
end
