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
)

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

	useUpstream := ask(reader, "Do you want to use upstream repositories? (y/n): ")
	err := configureRepos(useUpstream)
	if err != nil {
		printFancy("Error configuring repos")
		os.Exit(1)
	}
	clearScreen()
	extraPkgs := ask(reader, "Do you want to add extra packages? (y/n): ")
	if extraPkgs {
		appendExtraPackages()
	}
	clearScreen()
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

	installDeps := exec.Command("sudo", "pacman", "-Sy", "--noconfirm", "--needed" ,"base-devel", "git")
	installDeps.Stdout = os.Stdout
	installDeps.Stderr = os.Stderr
	fmt.Println("Installing required packages...")
	if err := installDeps.Run(); err != nil {
		fmt.Println("Failed to install required packages.")
		os.Exit(1)
	}

	src := "./mkedge/packages.x86_64.base"
	dest := "./packages.x86_64"
	input, err := os.ReadFile(src)
	if err != nil {
		fmt.Println("Failed to copy package base:", err)
		os.Exit(1)
	}
	os.WriteFile(dest, input, 0644)

	if err := os.Chmod("helper.sh", 0755); err != nil {
		fmt.Println("Failed to make mksteamos.sh executable:", err)
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

	match, err := filepath.Glob("SteamOS*.img")
	if err != nil || len(match) == 0 {
		fmt.Println("No SteamOS*.img file found.")
		return
	}
	imgFile := match[0]
	outFile := "steamos-edge.iso"

	fmt.Printf("Creating ISO from %s...\n", imgFile)
	copyCmd := exec.Command("dd", "if="+imgFile, "of="+outFile, "bs=4M", "status=progress")
	copyCmd.Stdout = os.Stdout
	copyCmd.Stderr = os.Stderr
	if err := copyCmd.Run(); err != nil {
		fmt.Println("Failed to create ISO:", err)
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

func configureRepos(useUpstream bool) error {
	src := "./mkedge/downstream.conf"
	if useUpstream {
		src = "./mkedge/upstream.conf"
	}
	dest := "./pacman.conf"
	input, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	return os.WriteFile(dest, input, 0644)
}

func appendExtraPackages() {
	extras := []string{
		"prismlauncher",
		"lutris-git",
		"opengamepadui-bin",
		"bottles",
		"gzdoom",
		"yay-bin",
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
