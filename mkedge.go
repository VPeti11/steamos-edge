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
	"time"
)

var enableColor = true

var colors = []string{
	"\033[31m",
	"\033[32m",
	"\033[34m",
	"\033[91m",
	"\033[92m",
	"\033[94m",
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
	helpFlag := flag.Bool("help", false, "Show this help menu")
	flag.Parse()

	if *helpFlag {
		fmt.Println(`Usage: mkedge [options]
	
	Options:
	  --mode        Repository mode: 1=Downstream, 2=Upstream, 3=32-bit
	  --extra       Add extra packages (modes 1,2 only)
	  --neptune     Use Neptune kernel (mode 2 only)
	  --build       Build the image after setup
	  --cowspace    Set cowspace size (default 2G. Use 'skip' to skip changing it
	  --bypass      Bypass checks
	  --cleanup     Starts from scratch
	  --help        Show this help menu`)
		os.Exit(0)
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
				fmt.Println("Invalid cowspace size. Skipping replacing CoWspace")
				*cowspaceFlag = "skip"
			}
		}
	}

	filename := ".test"

	if _, err := os.Stat(filename); err == nil {
		printFancy("Bypassing checks")
		time.Sleep(15 / 10 * time.Second)
	} else if os.IsNotExist(err) {
		if !*bypassFlag {
			if runtime.GOOS == "windows" {
				printFancy("USE WSL WE DO NOT SUPPORT WINDOWS!!!")
				os.Exit(1)
			}
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
	} else {
		printFancy("Error when checking test file")
	}

	printFancy("MKEDGE made by VPeti")
	time.Sleep(15 / 10 * time.Second)
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

	var zipName string
	switch mode {
	case 1:
		zipName = "boot64.zip"
		copyFileMust("./mkedge/packages.x86_64.base", "./packages.x86_64")
		copyFileMust("./mkedge/64dwn.sh", "./profiledef.sh")
		if *extraFlag || (*modeFlag == 0 && ask(reader, "Do you want to add extra packages? (y/n): ")) {
			appendExtraPackagesdwn()
		}
		if *neptuneFlag || (*modeFlag == 0 && ask(reader, "Do you want the Neptune kernel? (y/n): ")) {
			appendToFile("packages.x86_64", []string{"linux-neptune"})
			appendToFile("packages.x86_64", []string{"linux-firmware-neptune"})
			appendToFile("packages.x86_64", []string{"steamdeck-dsp"})
		} else {
			appendToFile("packages.x86_64", []string{"linux-firmware"})
		}
		copyFileMust("./mkedge/cust_64.sh", "./airootfs/root/customize_airootfs.sh")

	case 2:
		zipName = "boot64.zip"
		copyFileMust("./mkedge/packages.x86_64.base", "./packages.x86_64")
		copyFileMust("./mkedge/64.sh", "./profiledef.sh")
		if *extraFlag || (*modeFlag == 0 && ask(reader, "Do you want to add extra packages? (y/n): ")) {
			appendExtraPackages()
		}
		if *neptuneFlag || (*modeFlag == 0 && ask(reader, "Do you want the Neptune kernel? (y/n): ")) {
			appendToFile("packages.x86_64", []string{"linux-firmware-valve"})
		}
		copyFileMust("./mkedge/cust_64.sh", "./airootfs/root/customize_airootfs.sh")

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

	// --- Configure repos ---
	if err := configureRepos(mode); err != nil {
		printFancy("Error configuring repos")
		os.Exit(1)
	}

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

	if *liteFlag {
		handleLite(mode)
	} else {
		airootfsfile := "./airootfs/root/customize_airootfs.sh"
		if mode == 1 || mode == 2 {

			f, err := os.OpenFile(airootfsfile, os.O_APPEND|os.O_WRONLY, 0644)
			if err != nil {
				fmt.Println("Error opening customize_airootfs.sh:", err)
				return
			}
			defer f.Close()

			commands := `
		# Add Plasma Wayland autostart
		sudo bash -c 'cat > /home/deck/.bash_profile <<EOF
		if [[ -z $WAYLAND_DISPLAY && $XDG_VTNR -eq 1 ]]; then
		  exec dbus-run-session startplasma-wayland
		fi
		EOF'
		`
			_, err = f.WriteString(commands)
			if err != nil {
				fmt.Println("Error writing to customize_airootfs.sh:", err)
				return
			}
		} else {

			f, err := os.OpenFile(airootfsfile, os.O_APPEND|os.O_WRONLY, 0644)
			if err != nil {
				fmt.Println("Error opening customize_airootfs.sh:", err)
				return
			}
			defer f.Close()

			command := `
# Enable SDDM display manager
systemctl enable sddm
`
			_, err = f.WriteString(command)
			if err != nil {
				fmt.Println("Error writing to customize_airootfs.sh:", err)
				return
			}
		}
	}

	clearScreen()

	// --- Build ---
	build := *buildFlag
	if *modeFlag == 0 {
		build = ask(reader, "Do you want to build the image? (y/n): ")
	}

	if !build {
		fmt.Println("Exiting without building the image.")
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
		fmt.Println("Installing required packages...")
		if err := installDeps.Run(); err != nil {
			fmt.Println("Failed to install required packages.")
			os.Exit(1)
		}
	}

	clearScreen()
	if err := os.Chmod("helper.sh", 0755); err != nil {
		fmt.Println("Failed to make helper.sh executable:", err)
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

func appendExtraPackages() {
	extras := []string{
		"prismlauncher",
		"lutris-git",
		"opengamepadui-bin",
		"bottles",
		"gzdoom",
		"yay-bin",
		"antimicrox-git",
		"balena-etcher",
		"coolercontrol-bin",
		"betterdiscord-installer-bin",
		"moonlight-qt-bin",
		"peazip-qt-bin",
		"polychromatic-git",
		"protonup-qt-bin",
		"sunshine-bin",
	}
	appendToFile("packages.x86_64", extras)
}

func appendExtraPackagesdwn() {
	extras := []string{
		"prismlauncher",
		"lutris-git",
		"opengamepadui-bin",
		"bottles",
		"gzdoom",
		"yay-bin",
		"antimicrox-git",
		"coolercontrol-bin",
		"betterdiscord-installer-bin",
		"moonlight-qt-bin",
		"peazip-qt-bin",
		"polychromatic-git",
		"protonup-qt-bin",
	}
	appendToFile("packages.x86_64", extras)
}

func appendToFile(filename string, lines []string) {
	f, err := os.OpenFile(filename, os.O_APPEND|os.O_WRONLY, 0644)
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

func extractZip(zipPath string, destDir string) error {
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

		rc, err := f.Open()
		if err != nil {
			return fmt.Errorf("failed to open zipped file %s: %w", f.Name, err)
		}

		outFile, err := os.OpenFile(fpath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, f.Mode())
		if err != nil {
			rc.Close()
			return fmt.Errorf("failed to create file %s: %w", fpath, err)
		}

		_, err = io.Copy(outFile, rc)

		outFile.Close()
		rc.Close()

		if err != nil {
			return fmt.Errorf("failed to copy file content for %s: %w", fpath, err)
		}

		printFancy("Extracted: ", fpath)
	}

	return nil
}

func copyFileMust(src, dest string) {
	data, err := os.ReadFile(src)
	if err != nil {
		fmt.Println("Failed to copy:", src, err)
		os.Exit(1)
	}
	if err := os.WriteFile(dest, data, 0644); err != nil {
		fmt.Println("Failed to write:", dest, err)
		os.Exit(1)
	}
}

func runHelper(args ...string) {
	cmd := exec.Command(args[0], args[1:]...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin
	if err := cmd.Run(); err != nil {
		fmt.Println("Helper failed:", err)
		os.Exit(1)
	}
}

func replaceCowspaceFlag(newSize string) {
	if strings.ToLower(newSize) == "skip" {
		printFancy("Skipping cowspace replacement")
		return
	}
	if !regexp.MustCompile(`^\d+G$`).MatchString(newSize) {
		fmt.Println("Invalid cowspace size. Must be a number followed by 'G', e.g., 2G")
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
}

func checkInternet() bool {
	var cmd *exec.Cmd
	cmd = exec.Command("ping", "-c", "5", "1.1.1.1")
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
		fmt.Println("Invalid mode")
		return
	}

	lines, err := readLines(pkgFile)
	if err != nil {
		fmt.Println("Error reading package file:", err)
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
		fmt.Println("Error writing package file:", err)
		return
	}

	customFile := "./airootfs/root/customize_airootfs.sh"
	f, err := os.OpenFile(customFile, os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		fmt.Println("Error opening customize_airootfs.sh:", err)
		return
	}
	defer f.Close()

	commands := `
cat > /home/deck/.xinitrc <<EOF
exec startlxqt
EOF

sudo bash -c 'cat > /home/deck/.bash_profile <<EOF
if [[ -z $WAYLAND_DISPLAY && $XDG_VTNR -eq 1 ]]; then
  exec startx
fi
EOF'
`
	_, err = f.WriteString(commands)
	if err != nil {
		fmt.Println("Error writing to customize_airootfs.sh:", err)
		return
	}

	printFancy("Lite mode enabled successfully.")
}
