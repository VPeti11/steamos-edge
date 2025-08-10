package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

func main() {
	err := os.Chdir("..")
	if err != nil {
		fmt.Println("Error changing directory:", err)
		return
	}

	reader := bufio.NewReader(os.Stdin)
	fmt.Print("Enter new cowspace size (default 2G): ")
	input, _ := reader.ReadString('\n')
	input = strings.TrimSpace(input)
	if input == "" {
		input = "2G"
	}

	re := regexp.MustCompile(`cow_spacesize\s*=\s*\S+`)

	err = filepath.Walk(".", func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() && info.Name() == "airootfs" {
			return filepath.SkipDir
		}

		if info.IsDir() {
			return nil
		}

		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}

		newContent := re.ReplaceAllString(string(content), "cow_spacesize="+input)

		if newContent != string(content) {
			err = os.WriteFile(path, []byte(newContent), info.Mode())
			if err != nil {
				return err
			}
			fmt.Println("Updated:", path)
		}

		return nil
	})

	if err != nil {
		fmt.Println("Error:", err)
	}
}
