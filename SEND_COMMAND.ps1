$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = 'C:\Users\Acer Nitro V15\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonCommand) { $python = $pythonCommand.Source }
    else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCommand) { $python = $pythonCommand.Source }
        else {
            Write-Host 'Python 3 is required. Install Python 3 and try again.' -ForegroundColor Red
            Read-Host 'Press Enter to close'
            exit 1
        }
    }
}

function Invoke-AnimalCommand([hashtable]$Payload, [switch]$Quiet) {
    $json = $Payload | ConvertTo-Json -Depth 5
    $temp = Join-Path $PSScriptRoot 'command.tmp'
    $target = Join-Path $PSScriptRoot 'command.json'
    [System.IO.File]::WriteAllText($temp, $json + "`n", [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temp -Destination $target -Force

    $raw = & $python (Join-Path $PSScriptRoot 'folder_controller.py') --once
    $exitCode = $LASTEXITCODE
    if ($raw -and -not $Quiet) { Write-Host ($raw -join "`n") }
    if ($exitCode -ne 0) { throw 'Command failed. See result.json for details.' }
    return (($raw -join "`n") | ConvertFrom-Json)
}

while ($true) {
    Write-Host ''
    Write-Host 'Impossible Animals - Command menu' -ForegroundColor Cyan
    Write-Host '1. Show animal and breeding-pair counts'
    Write-Host '2. Suggest a pair, then record its stars'
    Write-Host '3. Add an animal'
    Write-Host '4. Show all pairs never tried'
    Write-Host '5. Count pairs by stars and view one star score'
    Write-Host '6. Edit a pair score by star group and pair number'
    Write-Host '0. Exit'
    $choice = Read-Host 'Choose 0-6'
    if ($null -eq $choice) { break }
    $choice = $choice.Trim()
    if ($choice -eq '0') { break }

    try {
        $command = $null
        switch ($choice) {
            '1' { $command = @{ action = 'summary' } }
            '2' { $command = @{ action = 'next' } }
            '4' { $command = @{ action = 'untried' } }
            '5' { $command = @{ action = 'top' } }
            '6' { $command = @{ action = 'top' } }
            '3' {
                $animal = (Read-Host 'Animal name').Trim()
                if (-not $animal) { throw 'Animal name cannot be empty.' }
                $command = @{ action = 'add'; animal = $animal }
            }
            default { throw 'Choose a number from 0 to 6.' }
        }

        if ($null -ne $command) {
            if ($choice -eq '1' -or $choice -eq '2' -or $choice -eq '4' -or $choice -eq '5' -or $choice -eq '6') { $response = Invoke-AnimalCommand $command -Quiet }
            else { $response = Invoke-AnimalCommand $command }
            if ($choice -eq '1' -and $response.ok) {
                Write-Host "`nAnimals: $($response.animal_count)"
                Write-Host "Pairs already bred: $($response.tried_pair_count)"
                Write-Host "Pairs not yet bred: $($response.untried_pair_count)"
                Write-Host "Total possible pairs: $($response.total_possible_pairs)"
                Write-Host "`nPairs by best-star score:"
                foreach ($group in $response.star_distribution) {
                    $scoreText = ([double]$group.stars).ToString('0.##', [Globalization.CultureInfo]::InvariantCulture)
                    Write-Host ("  {0} stars: {1} pairs" -f $scoreText, $group.pair_count)
                }
            }
            if ($choice -eq '4' -and $response.ok) {
                Write-Host "`nPair summary"
                Write-Host ("  Already tried: {0}" -f $response.tried_count)
                Write-Host ("  Not yet tried: {0}" -f $response.untried_count)
                Write-Host ("  Total possible: {0}" -f $response.total_pairs)
                $untriedPairs = @($response.pairs)
                if ($untriedPairs.Count -eq 0) {
                    Write-Host "`nAll possible pairs have been tried."
                } else {
                    Write-Host "`nAll untried pairs ($($untriedPairs.Count))" -ForegroundColor Yellow
                    for ($i = 0; $i -lt $untriedPairs.Count; $i++) {
                        $pair = $untriedPairs[$i]
                        Write-Host ("  {0}. {1} + {2}" -f ($i + 1), $pair[0], $pair[1])
                    }
                }
            }
            if ($choice -eq '5' -and $response.ok) {
                Write-Host "`nPair counts by best stars:"
                foreach ($group in $response.distribution) {
                    $scoreText = ([double]$group.stars).ToString('0.##', [Globalization.CultureInfo]::InvariantCulture)
                    Write-Host ("  {0} stars: {1} pairs" -f $scoreText, $group.pair_count)
                }

                $starsText = (Read-Host 'Which single star score do you want to view?').Trim()
                $limitText = (Read-Host 'How many pairs to show').Trim()
                $selectedStars = 0.0
                $pairLimit = 0
                $culture = [Globalization.CultureInfo]::InvariantCulture
                $style = [Globalization.NumberStyles]::Float
                if (-not [double]::TryParse($starsText, $style, $culture, [ref]$selectedStars) -or [double]::IsNaN($selectedStars) -or [double]::IsInfinity($selectedStars)) { throw 'Stars must be a finite number.' }
                if (-not [int]::TryParse($limitText, [ref]$pairLimit) -or $pairLimit -lt 1 -or $pairLimit -gt 5000) { throw 'Number of pairs must be a whole number from 1 to 5000.' }

                $filteredCommand = @{ action = 'top'; min_stars = $selectedStars; max_stars = $selectedStars; limit = $pairLimit }
                $filtered = Invoke-AnimalCommand $filteredCommand -Quiet
                Write-Host "`nPairs with $starsText stars: $($filtered.matched_pair_count); displaying $($filtered.pairs.Count):"
                foreach ($pair in $filtered.pairs) {
                    $scoreText = ([double]$pair.stars).ToString('0.##', [Globalization.CultureInfo]::InvariantCulture)
                    Write-Host ("  {0} stars: {1} + {2}" -f $scoreText, $pair.animal_a, $pair.animal_b)
                }
                if (-not $filtered.pairs -or $filtered.pairs.Count -eq 0) { Write-Host 'No pairs matched this star range.' }
            }
            if ($choice -eq '6' -and $response.ok) {
                Write-Host "`nCurrent pair counts by best stars:"
                foreach ($group in $response.distribution) {
                    $scoreText = ([double]$group.stars).ToString('0.################', [Globalization.CultureInfo]::InvariantCulture)
                    Write-Host ("  {0} stars: {1} pairs" -f $scoreText, $group.pair_count)
                }
                $currentStarsText = (Read-Host 'Which current star score do you want to correct?').Trim()
                $currentStars = 0.0
                $culture = [Globalization.CultureInfo]::InvariantCulture
                $style = [Globalization.NumberStyles]::Float
                if (-not [double]::TryParse($currentStarsText, $style, $culture, [ref]$currentStars) -or [double]::IsNaN($currentStars) -or [double]::IsInfinity($currentStars) -or $currentStars -lt 0) { throw 'Current stars must be a finite, non-negative number.' }

                $matches = Invoke-AnimalCommand @{ action = 'top'; min_stars = $currentStars; max_stars = $currentStars; limit = 5000 } -Quiet
                if ($matches.pairs.Count -eq 0) { throw "No pairs currently have $currentStarsText stars." }
                Write-Host "`nPairs with $currentStarsText stars:"
                for ($i = 0; $i -lt $matches.pairs.Count; $i++) {
                    $pair = $matches.pairs[$i]
                    Write-Host ("  {0}. {1} + {2}" -f ($i + 1), $pair.animal_a, $pair.animal_b)
                }
                $pairNumber = 0
                $pairNumberText = (Read-Host 'Which pair number do you want to edit?').Trim()
                if (-not [int]::TryParse($pairNumberText, [ref]$pairNumber) -or $pairNumber -lt 1 -or $pairNumber -gt $matches.pairs.Count) { throw "Enter a pair number from 1 to $($matches.pairs.Count)." }
                $selectedPair = $matches.pairs[$pairNumber - 1]
                $newStarsText = (Read-Host 'What should the corrected stars be?').Trim()
                $newStars = 0.0
                if (-not [double]::TryParse($newStarsText, $style, $culture, [ref]$newStars) -or [double]::IsNaN($newStars) -or [double]::IsInfinity($newStars) -or $newStars -lt 0) { throw 'New stars must be a finite, non-negative number.' }
                $edit = Invoke-AnimalCommand @{ action = 'edit_pair_score'; animal_a = $selectedPair.animal_a; animal_b = $selectedPair.animal_b; current_stars = $currentStars; new_stars = $newStars } -Quiet
                $bestScoreText = ([double]$edit.best_stars).ToString('0.################', [Globalization.CultureInfo]::InvariantCulture)
                Write-Host "Updated: $($edit.animal_a) + $($edit.animal_b); best score is now $bestScoreText stars." -ForegroundColor Green
            }
            if ($choice -eq '2' -and $response.pair) {
                $animalA = [string]$response.pair[0]
                $animalB = [string]$response.pair[1]
                Write-Host "`nSuggested pair" -ForegroundColor Cyan
                Write-Host "  $animalA + $animalB" -ForegroundColor Yellow

                $starsText = Read-Host 'Stars earned'
                $stars = 0.0
                if (-not [double]::TryParse($starsText, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$stars) -or $stars -lt 0 -or [double]::IsNaN($stars) -or [double]::IsInfinity($stars)) { throw 'Stars must be a finite, non-negative number.' }
                $recorded = Invoke-AnimalCommand @{ action = 'record'; animal_a = $animalA; animal_b = $animalB; stars = $stars } -Quiet
                $scoreText = ([double]$recorded.stars).ToString('0.################', [Globalization.CultureInfo]::InvariantCulture)
                Write-Host "Recorded: $animalA + $animalB = $scoreText stars (attempt $($recorded.attempts))" -ForegroundColor Green
            }
            if ($choice -eq '2' -and -not $response.pair) {
                Write-Host $response.message -ForegroundColor Yellow
            }
        }
    }
    catch {
        Write-Host $_.Exception.Message -ForegroundColor Red
    }

    [void](Read-Host 'Press Enter to return to the menu')
}

Write-Host 'Closed the command menu.' -ForegroundColor Cyan


