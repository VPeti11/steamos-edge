package main

import (
	"bufio"
	"fmt"
	"math/rand"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
	"io"
)

var enableExtra int

var enableColor = true

// Global reset code
const reset = "\033[0m"

// All supported ANSI colors
var colors = []string{
	"\033[31m", // Red
	//"\033[33m", // Yellow
	"\033[32m", // Green
	//"\033[36m", // Cyan
	"\033[34m", // Blue
	//"\033[35m", // Magenta
	"\033[91m", // Bright Red
	"\033[92m", // Bright Green
	//"\033[93m", // Bright Yellow
	"\033[94m", // Bright Blue
	//"\033[95m", // Bright Magenta
	//"\033[96m", // Bright Cyan
}

func copyFile(src, dst string) error {
	srcFile, err := os.Open(src)
	if err != nil {
		return err
	}
	defer srcFile.Close()

	dstFile, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer dstFile.Close()

	_, err = io.Copy(dstFile, srcFile)
	if err != nil {
		return err
	}

	// Optionally set executable permissions
	return os.Chmod(dst, 0755)
}


func isSudo() bool {
	// Check the effective user ID (EUID)
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
	fmt.Print("\033[0m") // Reset color but no newline
}

func randColor() string {
	return colors[rand.Intn(len(colors))]
}

func min(a, b, c int) int {
	if a < b && a < c {
		return a
	} else if b < c {
		return b
	}
	return c
}
func printFancy(args ...interface{}) {
	text := fmt.Sprint(args...)

	if !enableColor {
		fmt.Print(text + "\n") // Replace printFancy with raw print
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

func pause() {
	printFancy("Press ENTER to continue...")
	bufio.NewReader(os.Stdin).ReadBytes('\n')
}

func main() {
	clearScreen()
	if !isPacmanAvailable() {
		printFancy("This script requires pacman (Arch Linux). Are you sure you're on Arch?")
		os.Exit(1)
	}
	if isSudo() {
		printFancy("Running as root (sudo)")
	} else {
		printFancy("Not running as root")
		os.Exit(1)
	}

	printFancy("MKEDGE made by VPeti")
	time.Sleep(15 / 10 * time.Second)
	clearScreen()
	reader := bufio.NewReader(os.Stdin)

	if _, err := os.Stat("./work"); err == nil {
		reader := bufio.NewReader(os.Stdin)
		cont := ask(reader, "'./work' folder exists. Do you want to continue the build? (y/n): ")
		if cont {
			cmd := exec.Command("./helper.sh", "./")
			cmd.Stdout = os.Stdout
			cmd.Stderr = os.Stderr
			printFancy("Running helper.sh...")
			if err := cmd.Run(); err != nil {
				fmt.Println("helper.sh failed:", err)
				os.Exit(1)
			}
			os.Exit(0)
		} else {
			printFancy("Removing './work' and './out' folders...")
			os.RemoveAll("work")
			os.RemoveAll("out")
			printFancy("Folders removed. Continuing build.")
		}
	}


	printFancyInline("Which repositories do you want to use?\n[1] Downstream\n[2] Upstream\n[3] 32-bit\nEnter choice: ")
	input, _ := reader.ReadString('\n')
	input = strings.TrimSpace(input)

	var mode int

	enableExtra = 1
	switch input {
	case "1":
		mode = 1
		err := copyFile("./mkedge/64.sh", "./profiledef.sh")
		if err != nil {
			fmt.Println("Failed to copy 64-bit profile:", err)
			os.Exit(1)
		}

	case "2":
		mode = 2
		err := copyFile("./mkedge/64.sh", "./profiledef.sh")
		if err != nil {
			fmt.Println("Failed to copy 64-bit profile:", err)
			os.Exit(1)
		}

	case "3":
		mode = 3
		enableExtra = 0
		err := copyFile("./mkedge/32.sh", "./profiledef.sh")
		if err != nil {
			fmt.Println("Failed to copy 32-bit profile:", err)
			os.Exit(1)
		}
	default:
		printFancy("Invalid choice.")
		os.Exit(1)
	}

	err := configureRepos(mode)
	if err != nil {
		printFancy("Error configuring repos")
		os.Exit(1)
	}

	clearScreen()

	if enableExtra == 1 {

		extraPkgs := ask(reader, "Do you want to add extra packages? (y/n): ")
		if extraPkgs {
			appendExtraPackages()
		}
		clearScreen()
	}
	neptuneKernel := ask(reader, "Do you want the Neptune kernel? (y/n): ")
	if neptuneKernel {
		appendNeptuneKernel()
	}
	clearScreen()
	buildImage := ask(reader, "Do you want to build the image? (y/n): ")
	if !buildImage {
		fmt.Println("Exiting without building the image.")
		os.Exit(0)
	}

	pause()
	clearScreen()

	installDeps := exec.Command("sudo", "pacman", "-S", "--noconfirm", "--needed", "arch-install-scripts", "base-devel", "git", "squashfs-tools", "mtools", "dosfstools", "xorriso", "e2fsprogs", "erofs-utils", "libarchive", "libisoburn", "gnupg", "grub", "openssl", "python-docutils", "shellcheck")
	installDeps.Stdout = os.Stdout
	installDeps.Stderr = os.Stderr
	fmt.Println("Installing required packages...")
	if err := installDeps.Run(); err != nil {
		fmt.Println("Failed to install required packages.")
		os.Exit(1)
	}

	src := "./mkedge/packages.x86_64.base"
	dest := "./packages.x86_64"
	pkgData, err := os.ReadFile(src)
	if err != nil {
		fmt.Println("Failed to copy package base:", err)
		os.Exit(1)
	}
	if err := os.WriteFile(dest, pkgData, 0644); err != nil {
		fmt.Println("Failed to write package base:", err)
		os.Exit(1)
	}

	if err := os.Chmod("helper.sh", 0755); err != nil {
		fmt.Println("Failed to make helper.sh executable:", err)
		os.Exit(1)
	}

	clearScreen()

	cmd := exec.Command("sudo", "./helper.sh", "-v", ".", "/")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	fmt.Println("Building image...")
	if err := cmd.Run(); err != nil {
		fmt.Println("Build failed:", err)
		os.Exit(1)
	}

	clearScreen()

	if err := os.Chdir("out"); err != nil {
		fmt.Println("Failed to enter './out' folder:", err)
		os.Exit(1)
	}

	files, err := filepath.Glob("*.img")
	if err != nil || len(files) == 0 {
		fmt.Println("No .img files found in './out'.")
		os.Exit(1)
	}

	for _, imgFile := range files {
		isoFile := strings.TrimSuffix(imgFile, ".img") + ".iso"
		fmt.Printf("Converting %s to %s...\n", imgFile, isoFile)
		cmdStr := fmt.Sprintf("dd if=%q of=%q bs=4M status=progress", imgFile, isoFile)
		convert := exec.Command("sh", "-c", cmdStr)
		convert.Stdout = os.Stdout
		convert.Stderr = os.Stderr
		if err := convert.Run(); err != nil {
			fmt.Printf("Failed to convert %s: %v\n", imgFile, err)
		} else {
			fmt.Printf("Successfully created %s\n", isoFile)
		}
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
	inputBytes, err := os.ReadFile(src) // Correct type: []byte
	if err != nil {
		return fmt.Errorf("failed to read source config: %w", err)
	}

	err = os.WriteFile(dest, inputBytes, 0644) // []byte is expected
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

func appendNeptuneKernel() {
	appendToFile("packages.x86_64", []string{"linux-firmware-valve"})
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
