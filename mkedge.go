package main

import (
	"archive/zip"
	"bufio"
	"flag"
	"fmt"
	"io"
	"math/rand"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"sync"
	"syscall"
	"time"
)

var enableColor = true

var wg sync.WaitGroup

var colors = []string{
	"\033[31m",
	"\033[32m",
	"\033[34m",
	"\033[91m",
	"\033[92m",
	"\033[94m",
}

var bypassFlagChk bool

type stringSlice []string

func (s *stringSlice) String() string {
	return fmt.Sprintf("%v", *s)
}

func (s *stringSlice) Set(value string) error {
	*s = append(*s, value)
	return nil
}

func main() {
	clearScreen()
	// --- Flags ---
	modeFlag := flag.Int("mode", 0, "Repository mode: 1=Downstream, 2=Upstream, 3=32-bit")
	extraFlag := flag.Bool("extra", false, "Add extra packages (modes 1,2 only)")
	neptuneFlag := flag.Bool("neptune", false, "Use Neptune kernel (mode 2 only)")
	buildFlag := flag.Bool("build", false, "Build the image after setup")
	cowspaceFlag := flag.String("cowspace", "", "Set cowspace size (default 2G). Use 'skip' to skip changing it")
	bypassFlag := flag.Bool("bypass", false, "Bypass pacman/root checks")
	cleanupFlag := flag.Bool("cleanup", false, "Starts from scratch")
	liteFlag := flag.Bool("lite", false, "Lite mode")
	stagingFlag := flag.Bool("staging", false, "Use staging edge-repo")
	var addExtra stringSlice
	flag.Var(&addExtra, "addextra", "Add extra package (can be specified multiple times)")
	clFlag := flag.Bool("nocolor", false, "Bypass color")
	flag.Parse()

	if *clFlag {
		enableColor = false
	}

	if !*bypassFlag && *cleanupFlag {
		if !isSudo() {
			printFancy("Not running as root")
			os.Exit(1)
		}
		cleanup()
		os.Exit(0)
	}
	if *bypassFlag && *cleanupFlag {
		cleanup()
		os.Exit(0)
	}
	if *cowspaceFlag != "" {
		if *cowspaceFlag != "skip" {
			if !regexp.MustCompile(`^\d+G$`).MatchString(*cowspaceFlag) {
				printFancy("Invalid cowspace size. Skipping replacing CoWspace")
				*cowspaceFlag = "skip"
			}
		}
	}

	bypassFlagChk = *bypassFlag

	done := make(chan bool)
	go func() {
		doChecks()
		done <- true
	}()

loop:
	for {
		printFancy("Checking system...")
		printFancy("MKEDGE made by VPeti")
		time.Sleep(50 * time.Millisecond)
		clearScreen()

		select {
		case <-done:
			break loop
		default:
		}
	}

	printFancy("System checks passed. Continuing...")
	clearScreen()

	reader := bufio.NewReader(os.Stdin)

	// --- Handle ./work folder ---
	if _, err := os.Stat("./work"); err == nil {
		cont := *modeFlag != 0
		if *modeFlag == 0 {
			cont = ask(reader, "'./work' folder exists. Continue build? (y/n): ")
		}

		if cont {
			runHelper("sudo", "./helper.sh", "-v", ".", "/")
			clearScreen()
			printFancy("MKEDGE complete")
			os.Exit(0)
		} else {
			cleanup()
			printFancy("Folders removed. Continuing build.")
		}
	}

	clearScreen()

	// --- Choose repository mode ---
	mode := *modeFlag
	if mode == 0 {
		printFancyInline("Which repositories do you want to use?\n[1] Downstream\n[2] Upstream\n[3] 32-bit\nEnter choice: ")
		input, _ := reader.ReadString('\n')
		input = strings.TrimSpace(input)
		switch input {
		case "1":
			mode = 1
		case "2":
			mode = 2
		case "3":
			mode = 3
		default:
			printFancy("Invalid choice.")
			os.Exit(1)
		}
	}

	// --- Configure repos ---
	if err := configureRepos(mode); err != nil {
		printFancy("Error configuring repos")
		os.Exit(1)
	}

	var extraEnable bool
	var zipName string
	switch mode {
	case 1:
		zipName = "boot64.zip"
		copyFileMust("./mkedge/packages.x86_64.base", "./packages.x86_64")
		copyFileMust("./mkedge/64dwn.sh", "./profiledef.sh")
		if *extraFlag || (*modeFlag == 0 && ask(reader, "Do you want to add extra packages? (y/n): ")) {
			extraEnable = true
		}
		if *neptuneFlag || (*modeFlag == 0 && ask(reader, "Do you want the Neptune kernel? (y/n): ")) {
			appendToFile("packages.x86_64", []string{"linux-neptune"})
			appendToFile("packages.x86_64", []string{"linux-firmware-neptune"})
			appendToFile("packages.x86_64", []string{"steamdeck-dsp"})
		} else {
			appendToFile("packages.x86_64", []string{"linux-firmware"})
		}
		copyFileMust("./mkedge/cust_64.sh", "./airootfs/root/customize_airootfs.sh")
		clearScreen()
		handleStaging(*stagingFlag, *modeFlag, extraEnable, mode)

	case 2:
		zipName = "boot64.zip"
		copyFileMust("./mkedge/packages.x86_64.base", "./packages.x86_64")
		copyFileMust("./mkedge/64.sh", "./profiledef.sh")
		if *extraFlag || (*modeFlag == 0 && ask(reader, "Do you want to add extra packages? (y/n): ")) {
			extraEnable = true
		}
		if *neptuneFlag || (*modeFlag == 0 && ask(reader, "Do you want the Neptune kernel? (y/n): ")) {
			appendToFile("packages.x86_64", []string{"linux-firmware-valve"})
		}
		copyFileMust("./mkedge/cust_64.sh", "./airootfs/root/customize_airootfs.sh")
		clearScreen()
		handleStaging(*stagingFlag, *modeFlag, extraEnable, mode)

	case 3:
		zipName = "boot32.zip"
		copyFileMust("./mkedge/packages.i686.base", "./packages.i686")
		copyFileMust("./mkedge/32.sh", "./profiledef.sh")
		copyFileMust("./mkedge/cust_32.sh", "./airootfs/root/customize_airootfs.sh")
	default:
		printFancy("Invalid mode.")
		os.Exit(1)
	}

	copyFileMust("./mkedge/helper.sh", "./helper.sh")

	clearScreen()

	// --- Extract ---
	zipPath := filepath.Join("mkedge", zipName)
	printFancy("Extracting ", zipName, " to ", ".")
	if err := extractZip(zipPath, "."); err != nil {
		printFancy("Error during extraction: ", err)
		return
	}

	clearScreen()

	// --- Replace cowspace ---
	if *cowspaceFlag != "" {
		replaceCowspaceFlag(*cowspaceFlag)
	} else {
		replaceCowspacePrompt(reader)
	}

	lite := *liteFlag
	if *modeFlag == 0 {
		if lite == false {
			lite = ask(reader, "Do you want lite mode? (y/n): ")
		}
	}

	if lite {
		handleLite(mode)
	}

	clearScreen()

	var packagesToAdd []string

	if len(addExtra) > 0 {
		packagesToAdd = addExtra
	} else if *modeFlag == 0 {
		printFancy("Enter extra packages separated by space (leave empty to skip): ")
		input, _ := reader.ReadString('\n')
		input = strings.TrimSpace(input)
		if input != "" {
			packagesToAdd = strings.Fields(input)
		}
	}

	var packageFile string

	if mode == 1 || mode == 2 {
		packageFile = "packages.x86_64"
	} else {
		packageFile = "packages.i686"
	}

	if len(packagesToAdd) > 0 {
		appendToFile(packageFile, packagesToAdd)
		printFancy("Added extra packages:", packagesToAdd)
	}

	clearScreen()

	// --- Build ---
	build := *buildFlag
	if *modeFlag == 0 {
		build = ask(reader, "Do you want to build the image? (y/n): ")
	}

	if !build {
		printFancy("Exiting without building the image.")
		os.Exit(0)
	}

	clearScreen()

	// --- Install dependencies ---
	if !*bypassFlag {

		installDeps := exec.Command("sudo", "pacman", "-Sy", "--noconfirm", "--needed",
			"arch-install-scripts", "base-devel", "git", "squashfs-tools", "mtools", "dosfstools",
			"xorriso", "e2fsprogs", "erofs-utils", "libarchive", "libisoburn", "gnupg",
			"grub", "openssl", "python-docutils", "shellcheck")
		installDeps.Stdout = os.Stdout
		installDeps.Stderr = os.Stderr
		installDeps.Stdin = os.Stdin
		printFancy("Installing required packages...")
		if err := installDeps.Run(); err != nil {
			printFancy("Failed to install required packages.")
			os.Exit(1)
		}
	}

	clearScreen()
	if err := os.Chmod("helper.sh", 0755); err != nil {
		printFancy("Failed to make helper.sh executable:", err)
		os.Exit(1)
	}
	runHelper("sudo", "./helper.sh", "-v", ".", "/")
	clearScreen()
	printFancy("MKEDGE complete")
}

func isPacmanAvailable() bool {
	_, err := exec.LookPath("pacman")
	return err == nil
}

func ask(reader *bufio.Reader, prompt string) bool {
	printFancyInline(prompt)
	answer, _ := reader.ReadString('\n')
	answer = strings.TrimSpace(strings.ToLower(answer))
	return answer == "y" || answer == "yes"
}

func configureRepos(mode int) error {
	var src string

	switch mode {
	case 1:
		src = "./mkedge/downstream.conf"
	case 2:
		src = "./mkedge/upstream.conf"
	case 3:
		src = "./mkedge/32.conf"
	default:
		return fmt.Errorf("invalid mode: %d", mode)
	}

	dest := "./pacman.conf"
	inputBytes, err := os.ReadFile(src)
	if err != nil {
		return fmt.Errorf("failed to read source config: %w", err)
	}

	err = os.WriteFile(dest, inputBytes, 0644)
	if err != nil {
		return fmt.Errorf("failed to write destination config: %w", err)
	}

	return nil
}

func appendExtraPackages(mode string) {
	// common packages
	base := []string{
		"prismlauncher",
		"lutris-git",
		"bottles",
		"antimicrox-git",
		"polychromatic-git",
		"gzdoom",
	}

	pkgs := []string{
		"opengamepadui",
		"yay",
		"coolercontrol",
		"betterdiscord-installer",
		"moonlight-qt",
		"peazip-qt", // note: keep -qt so normal/dwn get peazip-qt-bin
		"protonup-qt",
		"sunshine",
		"balena-etcher", // normal only
		"ventoy",        // stage only
	}

	extras := make([]string, 0, len(pkgs))
	for _, p := range pkgs {
		name := p
		include := false
		suffix := ""

		switch mode {
		case "normal":
			if p == "ventoy" {
				continue
			}
			include = true
			if p != "balena-etcher" {
				suffix = "-bin"
			} // everything except balena-etcher gets -bin
		case "stage":
			if p == "balena-etcher" {
				continue
			}
			include = true
			if p == "peazip-qt" {
				name = "peazip"
			} // stage is plain "peazip"
		case "dwn":
			if p == "ventoy" || p == "sunshine" || p == "balena-etcher" {
				continue
			}
			include = true
			suffix = "-bin"
		case "dwnstage":
			if p == "ventoy" || p == "balena-etcher" {
				continue
			}
			include = true
			if p == "peazip-qt" {
				name = "peazip"
			} // dwnstage is plain "peazip"
		default:
			printFancy("Unknown mode:", mode)
			return
		}

		if include {
			extras = append(extras, name+suffix)
		}
	}

	appendToFile("packages.x86_64", append(base, extras...))
}

func appendToFile(filename string, lines []string) {
	// Wait for all previous goroutines to finish
	wg.Wait()

	f, err := os.OpenFile(filename, os.O_APPEND|os.O_WRONLY|os.O_CREATE, 0644)
	if err != nil {
		fmt.Printf("Failed to open %s: %v\n", filename, err)
		return
	}
	defer f.Close()

	for _, line := range lines {
		if _, err := f.WriteString(line + "\n"); err != nil {
			fmt.Printf("Failed to write to %s: %v\n", filename, err)
		}
	}
}

func copyFileMust(src, dest string) {
	data, err := os.ReadFile(src)
	if err != nil {
		fmt.Printf("Failed to copy: %s %v\n", src, err)
		os.Exit(1)
	}

	wg.Add(1)
	go func() {
		defer wg.Done()
		if err := os.WriteFile(dest, data, 0644); err != nil {
			fmt.Printf("Failed to write: %s %v\n", dest, err)
			os.Exit(1)
		}
	}()
}

func extractZip(zipPath, destDir string) error {
	absDest, err := filepath.Abs(destDir)
	if err != nil {
		return fmt.Errorf("failed to get absolute dest dir: %w", err)
	}

	r, err := zip.OpenReader(zipPath)
	if err != nil {
		return fmt.Errorf("failed to open zip file: %w", err)
	}
	defer r.Close()

	for _, f := range r.File {
		fpath := filepath.Join(destDir, f.Name)
		absFile, err := filepath.Abs(fpath)
		if err != nil {
			return fmt.Errorf("failed to get absolute path for %s: %w", fpath, err)
		}

		// Prevent zip slip
		if !strings.HasPrefix(absFile, absDest+string(os.PathSeparator)) && absFile != absDest {
			return fmt.Errorf("illegal file path: %s", fpath)
		}

		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(fpath, os.ModePerm); err != nil {
				return fmt.Errorf("failed to create directory %s: %w", fpath, err)
			}
			continue
		}

		if err := os.MkdirAll(filepath.Dir(fpath), os.ModePerm); err != nil {
			return fmt.Errorf("failed to create directory for file %s: %w", fpath, err)
		}

		// Open and fully read zip entry now
		rc, err := f.Open()
		if err != nil {
			return fmt.Errorf("failed to open zipped file %s: %w", f.Name, err)
		}

		data, err := io.ReadAll(rc)
		rc.Close()
		if err != nil {
			return fmt.Errorf("failed to read zipped file %s: %w", f.Name, err)
		}

		// Open output file
		outFile, err := os.OpenFile(fpath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, f.Mode())
		if err != nil {
			return fmt.Errorf("failed to create file %s: %w", fpath, err)
		}

		// Write in a goroutine
		wg.Add(1)
		go func(data []byte, outFile *os.File, fpath string) {
			defer wg.Done()
			defer outFile.Close()

			if _, err := outFile.Write(data); err != nil {
				fmt.Printf("Failed to write file content for %s: %v\n", fpath, err)
			} else {
				printFancy("Extracted: ", fpath)
			}
		}(data, outFile, fpath)
	}

	return nil
}

func runHelper(args ...string) {
	// Wait for all ongoing goroutines to finish first
	wg.Wait()

	cmd := exec.Command(args[0], args[1:]...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin
	if err := cmd.Run(); err != nil {
		printFancy("Helper failed:", err)
		os.Exit(1)
	}
}

func replaceCowspaceFlag(newSize string) {
	if strings.ToLower(newSize) == "skip" {
		printFancy("Skipping cowspace replacement")
		return
	}
	if !regexp.MustCompile(`^\d+G$`).MatchString(newSize) {
		printFancy("Invalid cowspace size. Must be a number followed by 'G', e.g., 2G")
		return
	}

	re := regexp.MustCompile(`cow_spacesize\s*=\s*\S+`)
	_ = filepath.Walk(".", func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if info.IsDir() {
			if info.Name() == "airootfs" || info.Name() == "mkedge" {
				return filepath.SkipDir
			}
			return nil
		}

		if info.Name() == "mkedge.go" {
			return nil
		}

		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}

		updated := re.ReplaceAllString(string(data), "cow_spacesize="+newSize)
		if updated != string(data) {
			if err := os.WriteFile(path, []byte(updated), info.Mode()); err != nil {
				return err
			}
			printFancy("Updated:", path)
		}
		return nil
	})
}

func replaceCowspacePrompt(reader *bufio.Reader) {
	clearScreen()
	printFancyInline("Enter new cowspace size (default 2G): ")
	newSize, _ := reader.ReadString('\n')
	newSize = strings.TrimSpace(newSize)
	if newSize == "" {
		newSize = "2G"
	}
	replaceCowspaceFlag(newSize)
}

func isSudo() bool {

	euid := os.Geteuid()
	return euid == 0
}

func printFancyInline(args ...interface{}) {
	text := fmt.Sprint(args...)

	if !enableColor {
		fmt.Print(text)
		return
	}

	for _, ch := range text {
		fmt.Print(randColor() + string(ch))
	}
	fmt.Print("\033[0m")
}

func randColor() string {
	return colors[rand.Intn(len(colors))]
}

func printFancy(args ...interface{}) {
	text := fmt.Sprint(args...)

	if !enableColor {
		fmt.Print(text + "\n")
		return
	}

	for _, ch := range text {
		fmt.Print(randColor() + string(ch))
	}
	fmt.Print("\033[0m\n")
}

func clearScreen() {
	fmt.Print("\033[H\033[2J")
}

func cleanup() {
	os.RemoveAll("work")
	os.RemoveAll("out")
	os.RemoveAll("grub")
	os.RemoveAll("neptune")
	os.RemoveAll("efiboot")
	os.RemoveAll("syslinux")
	os.Remove("packages.x86_64")
	os.Remove("packages.i686")
	os.Remove("helper.sh")
	os.Remove("pacman.conf")
	os.Remove("profiledef.sh")
	os.Remove("./airootfs/root/customize_airootfs.sh")
}

func checkInternet() bool {
	var cmd *exec.Cmd
	cmd = exec.Command("ping", "-c", "2", "1.1.1.1")
	err := cmd.Run()
	return err == nil
}

func readLines(filename string) ([]string, error) {
	file, err := os.Open(filename)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	var lines []string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}
	return lines, scanner.Err()
}

func writeLines(filename string, lines []string) error {
	file, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer file.Close()

	w := bufio.NewWriter(file)
	for _, line := range lines {
		fmt.Fprintln(w, line)
	}
	return w.Flush()
}

func handleLite(mode int) {

	var pkgFile string
	if mode == 1 || mode == 2 {
		pkgFile = "packages.x86_64"
	} else if mode == 3 {
		pkgFile = "packages.i686"
	} else {
		printFancy("Invalid mode")
		return
	}

	lines, err := readLines(pkgFile)
	if err != nil {
		printFancy("Error reading package file:", err)
		return
	}

	var newLines []string
	for _, line := range lines {
		if strings.HasPrefix(line, "plasma") {
			continue
		}
		newLines = append(newLines, line)
	}

	newLines = append(newLines, "lxqt", "xorg", "xorg-xinit", "xterm")

	err = writeLines(pkgFile, newLines)
	if err != nil {
		printFancy("Error writing package file:", err)
		return
	}

	customFile := "./airootfs/root/customize_airootfs.sh"
	RemoveMagicBrackets(customFile)
	f, err := os.OpenFile(customFile, os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		printFancy("Error opening customize_airootfs.sh:", err)
		return
	}
	defer f.Close()
	var commands string

	if mode == 3 {
		commands = `
cat > /home/deck/.xinitrc <<EOF
exec startlxqt
EOF
	
cat > /home/deck/.bash_profile <<'EOF'
if [[ -z $DISPLAY ]]; then
	exec startx
fi
EOF

sudo mkdir -p /etc/systemd/system/getty@tty1.service.d/
sudo bash -c 'cat > /etc/systemd/system/getty@tty1.service.d/override.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin deck --noclear %I \$TERM
EOF'
sudo systemctl enable getty@tty1
`
	} else {
		commands = `
cat > /home/deck/.xinitrc <<EOF
exec startlxqt
EOF
		
cat > /home/deck/.bash_profile <<'EOF'
if [[ -z $DISPLAY ]]; then
	exec startx
fi
EOF
`
	}
	_, err = f.WriteString(commands)
	if err != nil {
		printFancy("Error writing to customize_airootfs.sh:", err)
		return
	}

	printFancy("Lite mode enabled successfully.")
}

func RemoveMagicBrackets(filePath string) error {
	inputFile, err := os.Open(filePath)
	if err != nil {
		return fmt.Errorf("failed to open file: %w", err)
	}
	defer inputFile.Close()

	var outputLines []string
	scanner := bufio.NewScanner(inputFile)
	inBracket := false

	for scanner.Scan() {
		line := scanner.Text()
		if strings.Contains(line, "# MAGIC BRACKET") {
			inBracket = !inBracket
			continue
		}
		if !inBracket {
			outputLines = append(outputLines, line)
		}
	}

	if err := scanner.Err(); err != nil {
		return fmt.Errorf("error reading file: %w", err)
	}

	err = os.WriteFile(filePath, []byte(strings.Join(outputLines, "\n")), 0644)
	if err != nil {
		return fmt.Errorf("failed to write file: %w", err)
	}

	return nil
}

func handleStaging(stagingFlag bool, modeFlag int, extraEnable bool, amode int) {
	reader := bufio.NewReader(os.Stdin)
	stage := stagingFlag
	if modeFlag == 0 {
		if stage == false {
			stage = ask(reader, "Do you want to use staging repos? (y/n): ")
		}
	}

	if !stage {
		block := []string{
			"[edge-repo]",
			"SigLevel = Never",
			"Server = https://gitlab.com/edgedev1/edge-repo/-/raw/master/x86_64/",
			"Server = https://github.com/VPeti11/edge-repo/raw/refs/heads/master/x86_64/",
		}

		appendToFile("pacman.conf", block)

		heredoc := []string{
			`cat >> /etc/pacman.conf << EOF`,
			``,
			`[edge-repo]`,
			`SigLevel = Required DatabaseOptional`,
			"Server = https://gitlab.com/edgedev1/edge-repo/-/raw/master/x86_64/",
			`Server = https://github.com/VPeti11/edge-repo/raw/refs/heads/master/x86_64/`,
			`EOF`,
		}

		appendToFile("./airootfs/root/customize_airootfs.sh", heredoc)
	} else {
		block := []string{
			"[edge-repo]",
			"SigLevel = Never",
			"Server = https://github.com/VPeti11/edge-repo/raw/refs/heads/staging/x86_64/",
		}

		appendToFile("pacman.conf", block)

		heredoc := []string{
			`cat >> /etc/pacman.conf << EOF`,
			``,
			`[edge-repo]`,
			`SigLevel = Required DatabaseOptional`,
			`Server = https://github.com/VPeti11/edge-repo/raw/refs/heads/staging/x86_64/`,
			`EOF`,
		}

		appendToFile("./airootfs/root/customize_airootfs.sh", heredoc)
	}

	if extraEnable {
		mode := ""
		switch {
		case stage && amode == 1:
			mode = "dwnstage"
		case stage && amode != 1:
			mode = "stage"
		case !stage && amode == 1:
			mode = "dwn"
		case !stage && amode != 1:
			mode = "normal"
		}
		appendExtraPackages(mode)
	}

}

func isAnotherInstanceRunning() bool {
	// Get current PID
	pid := os.Getpid()

	// Use pgrep to find all processes with the exact name "mkedgescript"
	out, err := exec.Command("pgrep", "-x", "mkedgescript").Output()
	if err != nil {
		return false // no other processes found
	}

	// Split output and check if any PID is not the current one
	for _, line := range strings.Split(strings.TrimSpace(string(out)), "\n") {
		if line == "" {
			continue
		}
		if line != fmt.Sprintf("%d", pid) {
			return true
		}
	}
	return false
}

func checkDiskSpace(minMB uint64) bool {
	var stat syscall.Statfs_t
	if err := syscall.Statfs("/", &stat); err != nil {
		return false
	}
	freeMB := (stat.Bavail * uint64(stat.Bsize)) / 1024 / 1024
	return freeMB >= minMB
}

func checkFS() bool {
	out, err := exec.Command("df", "-T", "/").Output()
	if err != nil {
		return false
	}
	lines := strings.Split(string(out), "\n")
	if len(lines) < 2 {
		return false
	}
	fields := strings.Fields(lines[1])
	fsType := fields[1]
	return fsType != "ntfs" && fsType != "vfat" && fsType != "fat32"
}

func doChecks() {
	if bypassFlagChk {
		return
	}

	if runtime.GOOS == "windows" {
		printFancy("USE WSL WE DO NOT SUPPORT WINDOWS!!!")
		os.Exit(1)
	}

	// Check for required processes
	if isAnotherInstanceRunning() {
		printFancy("Another mkedgescript process is already running!")
		os.Exit(1)
	}

	// Check disk space
	if !checkDiskSpace(10 * 1024) { // 10 GB
		printFancy("Not enough disk space! Need at least 10GB free.")
		os.Exit(1)
	}

	// Check filesystem
	if !checkFS() {
		printFancy("Root filesystem is NTFS/FAT32. Use ext4/btrfs instead.")
		os.Exit(1)
	}

	// Existing checks
	if !isPacmanAvailable() {
		printFancy("This script requires pacman (Arch Linux)")
		os.Exit(1)
	}
	if !isSudo() {
		printFancy("Not running as root")
		os.Exit(1)
	}
	if !checkInternet() {
		printFancy("No internet")
		os.Exit(1)
	}
}
