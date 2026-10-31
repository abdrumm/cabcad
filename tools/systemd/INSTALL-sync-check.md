# CabCad sync-check install (no sudo)
    install -m755 tools/cabcad-sync-check ~/.local/bin/
    cp tools/systemd/cabcad-sync-*.service tools/systemd/cabcad-sync-check.timer ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now cabcad-sync-check.timer cabcad-sync-resume.service
    systemctl --user enable cabcad-sync-check.service
Laptop: edit REPOS at top of script if paths differ; set remotes to ssh URLs, e.g.
    git -C ~/Work/cabinet-gen remote set-url origin ssh://abdrumm@100.66.33.81/home/abdrumm/Work/git/cabinet-gen.git
    git -C ~/Work/omacad remote add imac ssh://abdrumm@100.66.33.81/home/abdrumm/Work/git/omacad.git
Needs key-based SSH (BatchMode) to the iMac. Log: ~/.local/state/cabcad-sync.log
