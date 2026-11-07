<#
  pg.ps1 —— 本地 PostgreSQL（免安装 zip 版）启停脚本
  用法（在项目根目录的普通 PowerShell 里执行）：
     .\pg.ps1 init      首次：初始化数据目录 + 建库 + 跑迁移
     .\pg.ps1 start     启动
     .\pg.ps1 stop      停止
     .\pg.ps1 status    查看状态
     .\pg.ps1 test      连接测试
     .\pg.ps1 migrate   只跑迁移
  注意：必须用【普通】PowerShell，不要用“以管理员身份运行”。
#>
param(
    [Parameter(Position=0)]
    [ValidateSet('init','start','stop','status','test','migrate')]
    [string]$Action = 'status'
)

$PgBin     = 'C:\pgsql\bin'
$PgData    = 'C:\pgdata'
$Port      = 15432
$DbName    = 'english_practice'
$PgUser    = 'postgres'
$MigrationDir = 'db\migrations'

$pgctl    = Join-Path $PgBin 'pg_ctl.exe'
$initdb   = Join-Path $PgBin 'initdb.exe'
$psql     = Join-Path $PgBin 'psql.exe'
$createdb = Join-Path $PgBin 'createdb.exe'

if (-not (Test-Path $pgctl)) {
    Write-Host "[FATAL] 找不到 $pgctl" -ForegroundColor Red
    Write-Host "        请先把 postgresql-16.x-windows-x64-binaries.zip 解压到 C:\pgsql" -ForegroundColor Yellow
    exit 1
}

function Warn-IfElevated {
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if ($isAdmin) {
        Write-Host "[WARN] 当前窗口疑似提权窗口。PostgreSQL 会拒绝在管理员权限下启动。" -ForegroundColor Yellow
        Write-Host "       请关掉，改用普通 PowerShell 重跑本脚本。" -ForegroundColor Yellow
    }
}

function Wait-Ready {
    for ($i = 1; $i -le 30; $i++) {
        & $psql -h 127.0.0.1 -p $Port -U $PgUser -d postgres -c "select 1" *> $null
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

Write-Host "==> $Action" -ForegroundColor Cyan

switch ($Action) {

    'init' {
        Warn-IfElevated
        if (Test-Path $PgData) {
            $items = Get-ChildItem $PgData -Force
            if ($items) {
                Write-Host "[FATAL] $PgData 已存在且非空，initdb 会拒绝执行。" -ForegroundColor Red
                Write-Host "        如需重来：先 .\pg.ps1 stop，再手动删除 C:\pgdata。" -ForegroundColor Yellow
                exit 1
            }
        }
        Write-Host "== 1/4 initdb ==" -ForegroundColor Cyan
        & $initdb -D $PgData -U $PgUser --encoding=UTF8 --locale=C --auth=trust
        if ($LASTEXITCODE -ne 0) { Write-Host "[FATAL] initdb 失败，把上面的报错整段贴出来。" -ForegroundColor Red; exit 1 }

        Write-Host "== 2/4 写入端口与监听地址 ==" -ForegroundColor Cyan
        Add-Content -Path (Join-Path $PgData 'postgresql.conf') -Encoding UTF8 `
            -Value "`n# --- local dev override ---`nport = $Port`nlisten_addresses = '127.0.0.1'`n"

        Write-Host "== 3/4 启动 ==" -ForegroundColor Cyan
        & $pgctl -D $PgData -l (Join-Path $PgData 'startup.log') -w start
        if (-not (Wait-Ready)) {
            Write-Host "[FATAL] 启动后连不上，请查看 C:\pgdata\startup.log" -ForegroundColor Red
            exit 1
        }

        Write-Host "== 4/4 建库 + 迁移 ==" -ForegroundColor Cyan
        & $createdb -h 127.0.0.1 -p $Port -U $PgUser $DbName 2>$null
        $migrations = @(Get-ChildItem -LiteralPath $MigrationDir -Filter '*.sql' | Sort-Object Name)
        if ($migrations.Count -gt 0) {
            foreach ($migration in $migrations) {
                Write-Host "==> migrate $($migration.Name)" -ForegroundColor Cyan
                & $psql -h 127.0.0.1 -p $Port -U $PgUser -d $DbName -v ON_ERROR_STOP=1 -f $migration.FullName
                if ($LASTEXITCODE -ne 0) { Write-Host "[FATAL] 迁移失败: $($migration.Name)" -ForegroundColor Red; exit 1 }
            }
        } else {
            Write-Host "[WARN] 没找到迁移文件，跳过迁移。" -ForegroundColor Yellow
        }

        Write-Host ""
        Write-Host "完成。DATABASE_URL = postgresql://${PgUser}@127.0.0.1:${Port}/${DbName}" -ForegroundColor Green
    }

    'start' {
        Warn-IfElevated
        & $pgctl -D $PgData -l (Join-Path $PgData 'startup.log') -w start
        if (Wait-Ready) { Write-Host "启动成功，端口 $Port" -ForegroundColor Green }
        else { Write-Host "[FATAL] 未就绪，看 C:\pgdata\startup.log" -ForegroundColor Red }
    }

    'stop' {
        & $pgctl -D $PgData -m fast -w stop
    }

    'status' {
        & $pgctl -D $PgData status
    }

    'test' {
        & $psql -h 127.0.0.1 -p $Port -U $PgUser -d $DbName -c "select current_database(), version();"
    }

    'migrate' {
        $migrations = @(Get-ChildItem -LiteralPath $MigrationDir -Filter '*.sql' | Sort-Object Name)
        if ($migrations.Count -eq 0) { Write-Host "[FATAL] 找不到迁移文件" -ForegroundColor Red; exit 1 }
        foreach ($migration in $migrations) {
            Write-Host "==> migrate $($migration.Name)" -ForegroundColor Cyan
            & $psql -h 127.0.0.1 -p $Port -U $PgUser -d $DbName -v ON_ERROR_STOP=1 -f $migration.FullName
            if ($LASTEXITCODE -ne 0) { Write-Host "[FATAL] 迁移失败: $($migration.Name)" -ForegroundColor Red; exit 1 }
        }
    }
}
