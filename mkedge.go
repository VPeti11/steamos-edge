package main

import (
	"archive/zip"
	"bufio"
	"crypto/sha512"
	"encoding/hex"
	"flag"
	"fmt"
	"io"
	"math/rand"
	"net"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"sync"
	"syscall"
	"time"
)

var enableColor = true
var debFl bool
var reset = "\033[0m"

var wg sync.WaitGroup

var colors = []string{
	"\033[31m",
	"\033[32m",
	"\033[34m",
	"\033[91m",
	"\033[92m",
	"\033[94m",
}

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
	bypassFlag := flag.Bool("bypass", false, "Bypass checks")
	cleanupFlag := flag.Bool("cleanup", false, "Starts from scratch")
	liteFlag := flag.Bool("lite", false, "Lite mode")
	stagingFlag := flag.Bool("staging", false, "Use staging edge-repo")
	var addExtra stringSlice
	flag.Var(&addExtra, "addextra", "Add extra package (can be specified multiple times)")
	clFlag := flag.Bool("nocolor", false, "Bypass color")
	nclFlag := flag.Bool("nocleanup", false, "Dont clean up")
	nsigFlag := flag.Bool("nosighandler", false, "Dont handle ctrl+c")
	debugFlag := flag.Bool("debug", false, "")
	animFlag := flag.Bool("noanim", false, "Disable animations")
	flag.Parse()

	debFl = *debugFlag

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
		}
	}

	if !*bypassFlag {
		if !*animFlag {
			checkAnim()
		} else {

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
		}
	}

	if !*nsigFlag {
		setupSignalHandler()
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

	if *cowspaceFlag != "" {
		if *cowspaceFlag != "skip" {
			if !regexp.MustCompile(`^\d+G$`).MatchString(*cowspaceFlag) {
				printFancy("Invalid cowspace size. Skipping replacing CoWspace")
				*cowspaceFlag = "skip"
			}
		}
	}

	// --- Replace cowspace ---
	if *cowspaceFlag != "" {
		replaceCowspaceFlag(*cowspaceFlag)
	} else {
		replaceCowspacePrompt(reader)
	}

	wg.Wait()
	clearScreen()

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

	clearScreen()
	if err := os.Chmod("helper.sh", 0755); err != nil {
		printFancy("Failed to make helper.sh executable:", err)
		os.Exit(1)
	}
	runHelper("sudo", "./helper.sh", "-v", ".", "/")
	if !*nclFlag {
		printFancy("Cleaning up...")
		cleanup()
	}
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
			if p == "sunshine" {
				// keep regular sunshine for normal
				suffix = ""
			} else if p != "balena-etcher" {
				suffix = "-bin"
			}
		case "stage":
			if p == "balena-etcher" {
				continue
			}
			include = true
			if p == "peazip-qt" {
				name = "peazip"
			} else if p == "sunshine" {
				name = "sunshine-beta"
				suffix = "-bin"
			}
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
			} else if p == "sunshine" {
				name = "sunshine-beta"
				suffix = "-bin"
			}
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
				os.Exit(1)
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
	semaphore := make(chan struct{}, 25) // Limit concurrency

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

		if info.Name() == "mkedgescript" {
			return nil
		}

		wg.Add(1)
		semaphore <- struct{}{} // Acquire slot

		go func(path string, info os.FileInfo) {
			defer wg.Done()
			defer func() { <-semaphore }() // Release slot

			data, err := os.ReadFile(path)
			if err != nil {
				printFancy("Failed to read file:", path, err)
				return
			}

			updated := re.ReplaceAllString(string(data), "cow_spacesize="+newSize)
			if updated != string(data) {
				if err := os.WriteFile(path, []byte(updated), info.Mode()); err != nil {
					printFancy("Failed to write file:", path, err)
					return
				}
				printFancy("Updated:", path)
			}
		}(path, info)

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
	timeout := 3 * time.Second
	conn, err := net.DialTimeout("tcp", "8.8.8.8:53", timeout)
	if err != nil {
		return false
	}
	conn.Close()
	return true
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

	cleanup()

	if !checkInternet() {
		clearScreen()
		printFancy("No internet")
		os.Exit(1)
	}

	if runtime.GOOS == "windows" {
		clearScreen()
		printFancy("USE WSL WE DO NOT SUPPORT WINDOWS!!!")
		os.Exit(1)
	}

	// Check for required processes
	if isAnotherInstanceRunning() {
		clearScreen()
		printFancy("Another mkedgescript process is already running!")
		os.Exit(1)
	}

	// Check disk space
	if !checkDiskSpace(10 * 1024) { // 10 GB
		clearScreen()
		printFancy("Not enough disk space! Need at least 10GB free.")
		os.Exit(1)
	}

	// Check filesystem
	if !checkFS() {
		clearScreen()
		printFancy("Root filesystem is NTFS/FAT32. Use ext4/btrfs instead.")
		os.Exit(1)
	}

	if !isPacmanAvailable() {
		clearScreen()
		printFancy("This script requires pacman (Arch Linux)")
		os.Exit(1)
	}
	if !isSudo() {
		clearScreen()
		printFancy("Not running as root")
		os.Exit(1)
	}

	if !debFl {

		if err := validateChecksums(); err != nil {
			clearScreen()
			printFancy("Error:", err)
			os.Exit(1)
		}

		if err := checkMkedgeScript(); err != nil {
			clearScreen()
			printFancy("MKEDGE checksum error!")
			os.Exit(1)
		}

	}

	installDeps := exec.Command("sudo", "pacman", "-Sy", "--noconfirm", "--needed",
		"arch-install-scripts", "base-devel", "git", "squashfs-tools", "mtools", "dosfstools",
		"xorriso", "e2fsprogs", "erofs-utils", "libarchive", "libisoburn", "gnupg",
		"grub", "openssl", "python-docutils", "shellcheck")
	installDeps.Stdout = io.Discard
	installDeps.Stderr = io.Discard
	if err := installDeps.Run(); err != nil {
		clearScreen()
		printFancy("Failed to install required packages.")
		os.Exit(1)
	}
}

func validateChecksums() error {
	expected := map[string]string{
		"mkedge/32.conf":              "d0c34c96c55389c55f85d2f788a2114547bb5b17bd64f995b0abf4ecf6549d290ee3cbd53259f6483d4c9d6154b5692a1e4e480285888abfb977b0c03f671e63",
		"mkedge/32.sh":                "e3b46f7bfe381f3c89e99b38a834c76993eba50cd5e43c91b7e1dd677b19f5f70d874fe722b5eb71cca024d1592f75a4a0d625dce3f06177d8d7dcc0cacd3f40",
		"mkedge/64dwn.sh":             "b1c158629c645e88f115e122b32dc52524e6a2e4d7247179d6e43bd8b284f1563b29b791cbcf46b1fa6c179e58bd751d88059ccedd94bdc0d3d0ca9f517e5890",
		"mkedge/64.sh":                "64fc4c088b6609a4d03f71de13784e3da209210883ec32b6fdb95da35d59613e8c2daa34a2ba54ce7533254969cf2b98a2273ecf3b378be3d03cfd7ee75098e1",
		"mkedge/boot32.zip":           "d4c8824ca478320463f07f37ba573b538a8354c5720bb135f1700a59c396adde5de4027a6923aff09c7631db52545978451178ed8d54eb37fea0b1c319da2694",
		"mkedge/boot64.zip":           "f3c19f6207e21792c90770ad9d381b1cda2ae396f36c3e20735871e03f219fd495a2330dacea9485f9f0747ad851fd6964dd39059c74dfa9e19c550033195970",
		"mkedge/cust_32.sh":           "129a2c01b6c2f579470a0b64c56c70f9582ec62e7a1f3707438749c9649086cf8690fc524c1a84a48260ffaef15e95a780bbaf003e2b61b32b24a1b9746d105a",
		"mkedge/cust_64.sh":           "7d49d63423118b9349de04635f63d7d2807c36af1c78836c99243128b9ccaad544ec4dc12b929913d4ee926366cb659e99ac7032f62363b6265e07186460c01b",
		"mkedge/downstream.conf":      "02a2b7b4046cab7a5a20b60eba0a6a3d11c3990b0dbff8f7cebf0374c4a065bd2964d3a7556e2e745cd01bf73b431ca43d112d8dfa3fe845637ee45b60b5f2ba",
		"mkedge/helper.sh":            "1d24dfbaf369bfbe0d1dc5a64c661114f5a0f4f0c24d802eb030b7205b4389cb625fd625c8ffe9fed3a407cee079024050228113f806c2b0c189bc29fc412899",
		"mkedge/packages.i686.base":   "31107a1d2f9fca2857348621ff717014b81004ffe831fac4ba7e2269d2198807a2e473c7b189ed290f8c620a22c8cf8dafc21d64671ab0b6171be8c53c132f94",
		"mkedge/packages.x86_64.base": "657df57e920a49c93a15def5bc22d1a4a71fa2bfaf4d3a98169008658cff151e51538d4cdfec55c407f94a980cb19d8a38e568550da812b75224613335a4503d",
		"mkedge/upstream.conf":        "4987290b3a17b33108ffa455149dc136d7a73e68a1fa2d893358d38c681612f1cb25d661624188a7192138ab1866831094cd7d31d6b375f424303809bd4968a5",
	}

	return filepath.Walk("mkedge", func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}
		if filepath.Ext(path) == ".asc" || filepath.Ext(path) == ".sig" || filepath.Ext(path) == ".sha512" {
			return nil
		}

		f, err := os.Open(path)
		if err != nil {
			return fmt.Errorf("failed to open %s: %v", path, err)
		}
		defer f.Close()

		h := sha512.New()
		if _, err := io.Copy(h, f); err != nil {
			return fmt.Errorf("failed to read %s: %v", path, err)
		}
		sum := hex.EncodeToString(h.Sum(nil))

		expectedSum, ok := expected[path]
		if !ok {
			//return fmt.Errorf("no checksum for %s", path)
		}
		if sum != expectedSum {
			return fmt.Errorf("checksum mismatch for %s", path)
		}
		return nil
	})
}

func checkMkedgeScript() error {
	// Read expected hash from ./mkedge/script.sha512
	data, err := os.ReadFile("./mkedge/script.sha512")
	if err != nil {
		return fmt.Errorf("failed to read checksum file: %w", err)
	}
	expected := strings.TrimSpace(string(data))

	// Get the path of the running executable
	exePath, err := os.Executable()
	if err != nil {
		return fmt.Errorf("failed to get executable path: %w", err)
	}

	// Open the running executable
	f, err := os.Open(exePath)
	if err != nil {
		return fmt.Errorf("failed to open executable: %w", err)
	}
	defer f.Close()

	// Compute SHA512
	hasher := sha512.New()
	if _, err := io.Copy(hasher, f); err != nil {
		return fmt.Errorf("failed to hash executable: %w", err)
	}
	actual := hex.EncodeToString(hasher.Sum(nil))

	// Compare
	if actual != expected {
		return fmt.Errorf("checksum mismatch: expected %s, got %s", expected, actual)
	}

	return nil
}

func onCtrlC() {
	fmt.Printf("\n")
	printFancy("Ctrl+C detected! Running cleanup function...")
	cleanup()
}

func setupSignalHandler() {
	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigs
		onCtrlC()
		os.Exit(1)
	}()
}

func checkAnim() {
	rand.Seed(time.Now().UnixNano())

	done := make(chan bool, 1) // buffered to avoid blocking

	go func() {
		doChecks()
		done <- true
	}()

	spinner := []string{"⠋", "⠙", "⠸", "⠴", "⠦", "⠇"}
	pulsing := []string{".    ", "..   ", "...  ", " ....", "  ...", "   ..", "    ."}
	matrix := []string{"[=     ]", "[==    ]", "[===   ]", "[====  ]", "[===== ]", "[======]", "[===== ]", "[====  ]", "[===   ]", "[==    ]", "[=     ]"}
	stick1 := `  o
 /|\
 / \   o`
	stick2 := `  o
 /|\
 / \    
      o`
	stick3 := `  o
 /|\
 / \      
       o`

	tape := `   ____________________________
 /|............................|
| |: Harman/Kardon Testing Tape :|
| |:     "Induljon a banzáj!"   :|
| |:     ,-.   _____   ,-.      :|
| |:    ( ')) [_____] ( '))     :|
|v|:     '-   ' ' '   -'        :|
|||:     ,______________.       :|
|||...../::::o::::::o::::\.....|
|^|..../:::O::::::::::O:::\....|
|/` + "`---/--------------------`---|\n.___/ /====/ /=//=/ /====/____/\n     --------------------"

	animations := [][]string{
		spinner,
		pulsing,
		matrix,
		{stick1, stick2, stick3},
		{tape},
	}

	textColor := colors[0]

	// Goroutine to update top text color every 50ms
	go func() {
		for {
			select {
			case <-done:
				return
			default:
				textColor = colors[rand.Intn(len(colors))]
				time.Sleep(50 * time.Millisecond)
			}
		}
	}()

loop:
	for {
		idx := rand.Intn(len(animations))
		anim := animations[idx]

		var sleepDur time.Duration
		switch idx {
		case 0:
			sleepDur = 150 * time.Millisecond
		case 1:
			sleepDur = 250 * time.Millisecond
		case 2:
			sleepDur = 300 * time.Millisecond
		case 3:
			sleepDur = 450 * time.Millisecond
		case 4:
			sleepDur = 1200 * time.Millisecond // slower for tape
		default:
			sleepDur = 300 * time.Millisecond
		}

		for i := 0; i < len(anim); i++ {
			clearScreen()
			fmt.Printf("%sChecking system...%s\n", textColor, reset)
			fmt.Printf("%sMKEDGE made by VPeti%s\n\n", textColor, reset)
			printFancy(anim[i])

			// Wait but exit immediately if done
			select {
			case <-done:
				break loop
			case <-time.After(sleepDur):
			}
		}
	}
}
