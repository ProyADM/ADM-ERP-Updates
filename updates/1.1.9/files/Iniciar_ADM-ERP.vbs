' ============================================================
' Iniciar_ADM-ERP.vbs - Lanzador de ADM-ERP
' ============================================================
' Lo genera el instalador (o se usa tal cual en desarrollo). Responsabilidades:
'   0. MODO RELANZADOR (`/sinavegador`): asi lo invoca `modules/shared/relanzar_app.py`
'      al reiniciar por una actualizacion. En ese modo NO se abre el navegador y NO se
'      muestra ningun cartel: la pestana que ya estaba abierta se recupera sola (el
'      frontend espera el reinicio en `esperarReinicio`, `frontend/app.js`). Antes
'      quedaban DOS ventanas del navegador para UNA sola aplicacion (medido el
'      02/10/2026, al aplicar la 1.1.8 desde la 1.1.7).
'   1. Elegir el interprete: PRIMERO el Python portatil de {app}\python\python.exe
'      (asi la PC destino NO necesita Python instalado); si no esta, el del PATH.
'      El PUERTO que se mira en todo el script sale de `APP_PORT` del entorno (el
'      mismo que lee `app.py`), 5000 por defecto: ver `PuertoDeEntorno`.
'   2. Desencriptar la configuracion si hace falta ({app}\erp.env.encrypted ->
'      {app}\.env.local). config.py exige .env.local en su directorio de trabajo.
'   3. Si hay un REINICIO PENDIENTE (bandera que deja la app cuando no pudo
'      relanzarse), cerrar TODOS los procesos que ESCUCHAN el puerto y arrancar: el
'      atajo de "ya esta corriendo" dejaria vivo el codigo viejo.
'   4. Arrancar la app (salvo que ya este corriendo en el puerto).
'   5. Puerto ocupado (SOLO en el doble clic del usuario; en modo relanzador no corre,
'      ver `AccionPuertoOcupado`): si el que escucha es OTRO programa, avisar y no
'      abrir nada; si es ADM-ERP y hay una actualizacion aplicada sin reiniciar,
'      ofrecer reiniciar.
'   6. Abrir el navegador (salvo en modo relanzador).
'
' IMPORTANTE (esquema de actualizaciones): el canal diferencial actualiza el
' codigo de la app (app.py, modules\, frontend\) y ESTE ARCHIVO. Por eso vive en la
' RAIZ del proyecto y no en installer\ (esa carpeta esta excluida del canal): su
' ruta en el cliente es {app}\Iniciar_ADM-ERP.vbs, asi que el manifiesto lo publica
' como un archivo mas y los arreglos del lanzador llegan SIN reinstalar el .exe.
' La carpeta python\ la instala el .exe y queda FUERA del manifest: asi el updater
' nunca reemplaza el interprete con el que se esta ejecutando.
' ============================================================

Option Explicit

Dim objShell, objFSO, objWMIService, colItems
Dim appDir, pyExe, pywExe, puerto, cmd, encriptado, destino, masterKey, linea
Dim yaCorre, sinNavegador, i, accion
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

appDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' El puerto sale de `APP_PORT` del entorno --la MISMA variable que lee `app.py`--,
' con 5000 por defecto. Antes estaba hardcodeado y con un puerto distinto (los
' despliegues LAN del doc C8) el lanzador miraba el puerto EQUIVOCADO: no veia la
' app corriendo (arrancaba una segunda instancia) y la rama de la bandera de
' reinicio cerraba los procesos de OTRO puerto.
puerto = PuertoDeEntorno()

' --- 0. Modo relanzador: `/sinavegador` -------------------------------------
' Lo pasa `modules/shared/relanzar_app.py` al reiniciar por una actualizacion. La
' pestana viva se recarga sola cuando el servidor vuelve, asi que abrir otra ventana
' es lo que dejaba DOS ventanas para UNA aplicacion. En este modo tampoco corre nada
' de la seccion 5: un cartel modal detras del navegador no lo ve nadie.
sinNavegador = False
For i = 0 To WScript.Arguments.Count - 1
    If LCase(Trim(WScript.Arguments(i))) = "/sinavegador" Then sinNavegador = True
Next

' Que hacer cuando YA hay algo escuchando el puerto (lo decide la seccion 5).
Const ACCION_NADA = 0          ' abrir el navegador sobre la app que ya corre
Const ACCION_REINICIAR = 1     ' cerrar la instancia que escucha y arrancar de nuevo
Const ACCION_NO_ARRANCAR = 2   ' el puerto lo ocupa OTRO programa: ni arrancar ni abrir

' --- 1. Interprete: portatil primero, luego el del sistema -------------------
pyExe = appDir & "\python\python.exe"
If Not objFSO.FileExists(pyExe) Then
    pyExe = "python.exe"   ' del PATH
End If

' --- 2. Desencriptar configuracion si falta .env.local ----------------------
encriptado = appDir & "\erp.env.encrypted"
destino = appDir & "\.env.local"
If objFSO.FileExists(encriptado) And Not objFSO.FileExists(destino) Then
    masterKey = ""
    If objFSO.FileExists(appDir & "\.master.key") Then
        Dim f
        Set f = objFSO.OpenTextFile(appDir & "\.master.key", 1)
        masterKey = Trim(f.ReadAll)
        f.Close
    End If
    linea = "cmd /c cd /d """ & appDir & """ && "
    If masterKey <> "" Then
        linea = linea & "set SIDESYS_MASTER_KEY=" & masterKey & " && "
    End If
    linea = linea & """" & pyExe & """ crypto_utils.py --decrypt """ & _
            encriptado & """ --output """ & destino & """"
    objShell.Run linea, 0, True
    ' Si se desencripto bien, el archivo cifrado ya no hace falta en la PC
    If objFSO.FileExists(destino) Then
        On Error Resume Next
        objFSO.DeleteFile encriptado, True
        On Error Goto 0
    End If
End If

' --- 3. Reinicio pendiente: cerrar los procesos que ESCUCHAN el puerto -------
' Solo los PID que ESCUCHAN el puerto (parseados de netstat -ano): NO se matan
' pythons ajenos. El que escucha es, por construccion, la app vieja.
If objFSO.FileExists(BanderaReinicio()) Then
    CerrarEscuchasYEsperar puerto
End If

' --- 4. Arrancar la app si no esta corriendo --------------------------------
' El default sigue siendo "ya esta corriendo" (chequeo del puerto + WMI).
' Chequeo principal: ¿hay algo escuchando en el puerto? (no depende de WMI, que
' puede estar restringido por politicas). WMI queda como respaldo.
yaCorre = EstaEscuchando(puerto)

If Not yaCorre Then
    On Error Resume Next
    Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")
    If Err.Number = 0 Then
        Set colItems = objWMIService.ExecQuery("Select * from Win32_Process Where Name = 'python.exe' and CommandLine like '%app.py%'")
        If Err.Number = 0 Then
            If colItems.Count > 0 Then yaCorre = True
        End If
    End If
    On Error Goto 0
End If

' --- 5. Puerto ocupado: avisar u ofrecer reiniciar (solo doble clic) ----------
' En modo relanzador esta seccion NO hace nada (lo garantiza la primera linea de
' `AccionPuertoOcupado`): el relanzador ya resolvio el puerto y el reinicio tiene
' que ser silencioso.
If yaCorre Then
    accion = AccionPuertoOcupado(puerto)
    If accion = ACCION_NO_ARRANCAR Then
        ' El puerto lo ocupa OTRO programa: no hay nada que arrancar y abrir el
        ' navegador mostraria ese otro servicio (es el "abre la app vieja" del
        ' 02/10/2026). Se sale sin abrir nada: el cartel ya explico el motivo.
        WScript.Quit 0
    ElseIf accion = ACCION_REINICIAR Then
        ' El usuario pidio reiniciar: `AccionPuertoOcupado` ya cerro los procesos
        ' que escuchaban y espero el puerto, asi que el arranque de abajo corre.
        yaCorre = False
    End If
End If

If Not yaCorre Then
    ' El cwd importa: config.py busca .env.local en el directorio actual
    objShell.CurrentDirectory = appDir
    objShell.Run "cmd /c cd /d """ & appDir & """ && start /B """" """ & _
                 pyExe & """ app.py", 0, False
    WScript.Sleep 10000
End If

' --- 6. Abrir el navegador (salvo en modo relanzador) -----------------------
If Not sinNavegador Then
    objShell.Run "http://localhost:" & puerto, 1, False
End If

' ============================================================
' Puerto de la app: `APP_PORT` del entorno (el MISMO que lee `app.py`), 5000 si no
' esta definida o no es un puerto valido. `ExpandEnvironmentStrings` devuelve el
' nombre tal cual cuando la variable no existe ("%APP_PORT%"), y eso es lo que se
' descarta aca.
' ============================================================
Function PuertoDeEntorno()
    Dim valor, n
    PuertoDeEntorno = 5000
    valor = Trim(objShell.ExpandEnvironmentStrings("%APP_PORT%"))
    If valor = "" Or valor = "%APP_PORT%" Then Exit Function
    If Not IsNumeric(valor) Then Exit Function
    n = CLng(valor)
    If n >= 1 And n <= 65535 Then PuertoDeEntorno = n
End Function

' ============================================================
' Ruta de la bandera de reinicio pendiente (junto a update_status.json).
' ============================================================
Function BanderaReinicio()
    BanderaReinicio = CarpetaDatos() & "\reinicio_pendiente.flag"
End Function

' ============================================================
' Carpeta de datos de la app en la PC (%PROGRAMDATA%\SidesysERP): la MISMA que usa
' `app.py` para `update_status.json` y para la bandera de reinicio. El respaldo a
' "C:\ProgramData" es el que ya tenia la ruta de la bandera: si la variable de
' entorno no se puede expandir, `ExpandEnvironmentStrings` devuelve el nombre tal
' cual y sin el respaldo la ruta quedaria relativa.
' ============================================================
Function CarpetaDatos()
    Dim pdata
    pdata = objShell.ExpandEnvironmentStrings("%PROGRAMDATA%")
    If pdata = "" Or pdata = "%PROGRAMDATA%" Then
        pdata = "C:\ProgramData"
    End If
    CarpetaDatos = pdata & "\SidesysERP"
End Function

' ============================================================
' ¿Que hacer con el puerto ocupado? Devuelve ACCION_NADA, ACCION_REINICIAR o
' ACCION_NO_ARRANCAR (ver las Const de arriba).
'
' PRIMERA linea: con `/sinavegador` (modo relanzador) sale sin hacer NADA. Es la
' garantia de que un reinicio desatendido no puede quedar esperando un cartel modal
' detras del navegador; el test la exige textualmente.
'
' Los carteles son SOLO de este camino (doble clic del usuario):
'   - el que escucha es OTRO programa  -> se avisa y no se abre nada;
'   - es ADM-ERP y hay una actualizacion APLICADA sin reiniciar -> se ofrece
'     reiniciar (Si = cerrar la instancia y arrancar de nuevo; No = abrir el
'     navegador con la app que ya corre);
'   - es ADM-ERP y no hay nada que aplicar -> no se dice nada (se abre el
'     navegador, como siempre): un cartel en cada doble clic seria un estorbo.
' ============================================================
Function AccionPuertoOcupado(p)
    Dim pid, nuestra
    AccionPuertoOcupado = ACCION_NADA
    If sinNavegador Then Exit Function
    If PidsEscuchando(p) = "" Then Exit Function

    pid = PidEscuchando(p)
    nuestra = EsNuestraApp(pid)
    If IsEmpty(nuestra) Then
        ' No se pudo preguntar (WMI restringido por politicas): se trata como
        ' nuestra y se sigue el camino de siempre. Un cartel de alarma en cada
        ' doble clic seria peor que el silencio. DECLARADO, no defendido.
    ElseIf nuestra = False Then
        MsgBox "ADM-ERP no puede arrancar: el puerto " & p & " esta ocupado por otro " & _
               "programa (PID " & pid & ")." & vbCrLf & vbCrLf & _
               "Cerra ese programa y volve a intentar la apertura.", _
               vbExclamation, "ADM-ERP"
        AccionPuertoOcupado = ACCION_NO_ARRANCAR
        Exit Function
    End If

    ' ADM-ERP ya corre: reiniciar SOLO si hay algo que aplicar (una actualizacion
    ' aplicada en disco que este proceso viejo todavia no tiene cargada).
    If Not HayActualizacionAplicada() Then Exit Function
    If MsgBox("ADM-ERP ya esta abierto y hay una actualizacion aplicada sin reiniciar." & _
              vbCrLf & vbCrLf & "Reiniciar ahora? Se cierra la aplicacion y se vuelve " & _
              "a abrir." & vbCrLf & "Si elegis No, se abre el navegador con la " & _
              "aplicacion que ya esta corriendo.", _
              vbYesNo + vbQuestion, "ADM-ERP") <> vbYes Then Exit Function

    CerrarEscuchasYEsperar p
    AccionPuertoOcupado = ACCION_REINICIAR
End Function

' ============================================================
' ¿El proceso `pid` (el que escucha el puerto) es ADM-ERP? Mismo criterio que el
' respaldo por WMI de la seccion 4: interprete de Python con `app.py` en la linea
' de comandos. Tres estados:
'   True  = se pudo preguntar y ES nuestra app
'   False = se pudo preguntar y NO es nuestra app (intruso)
'   Empty = WMI no respondio (politicas): no se puede afirmar NADA
' El llamador trata el Empty como "nuestra" (fail-open al comportamiento de
' siempre). Es una HEURISTICA declarada: no se defiende.
' ============================================================
Function EsNuestraApp(pid)
    Dim svc, col, proc, lineaCmd, nombre
    EsNuestraApp = Empty
    If pid = "" Then Exit Function
    On Error Resume Next
    Set svc = GetObject("winmgmts:\\.\root\cimv2")
    If Err.Number <> 0 Then
        Err.Clear
        On Error Goto 0
        Exit Function
    End If
    Set col = svc.ExecQuery("Select Name, CommandLine from Win32_Process Where ProcessId = " & pid)
    If Err.Number <> 0 Then
        Err.Clear
        On Error Goto 0
        Exit Function
    End If
    For Each proc In col
        nombre = LCase("" & proc.Name)
        lineaCmd = LCase("" & proc.CommandLine)
        If (nombre = "python.exe" Or nombre = "pythonw.exe") And InStr(lineaCmd, "app.py") > 0 Then
            EsNuestraApp = True
        Else
            EsNuestraApp = False
        End If
    Next
    On Error Goto 0
End Function

' ============================================================
' ¿El updater dejo una actualizacion APLICADA sin reiniciar? Es el UNICO caso en
' el que reiniciar la instancia que ya corre sirve para algo. Se lee el MISMO
' `update_status.json` que escribe la app y se busca el estado por texto: para
' esto no hace falta un parser de JSON.
' ============================================================
Function HayActualizacionAplicada()
    Dim archivoEstado, texto, ruta
    HayActualizacionAplicada = False
    ruta = CarpetaDatos() & "\update_status.json"
    If Not objFSO.FileExists(ruta) Then Exit Function
    On Error Resume Next
    Set archivoEstado = objFSO.OpenTextFile(ruta, 1)
    If Err.Number <> 0 Then
        Err.Clear
        On Error Goto 0
        Exit Function
    End If
    texto = archivoEstado.ReadAll
    archivoEstado.Close
    On Error Goto 0
    If InStr(texto, "aplicada_sin_reinicio") > 0 Then HayActualizacionAplicada = True
End Function

' ============================================================
' Cierra TODOS los procesos que ESCUCHAN el puerto y espera (hasta 15 s) a que el
' socket quede libre. Lo usan DOS caminos -el reinicio por bandera (seccion 3) y el
' "Si, reiniciar" del cartel de puerto ocupado-, asi que vive en un solo lugar:
' antes estaba embebido en la seccion 3 y el parseo de netstat habria quedado
' duplicado. Se cierran TODOS (no solo el primero): lo normal es el mismo proceso
' con IPv4 + IPv6, pero si fueran dos, dejar uno vivo haria fallar el arranque.
' ============================================================
Sub CerrarEscuchasYEsperar(p)
    Dim pidEscucha, intentoEspera
    For Each pidEscucha In Split(PidsEscuchando(p), ";")
        If pidEscucha <> "" Then
            objShell.Run "cmd /c taskkill /F /PID " & pidEscucha, 0, True
        End If
    Next
    For intentoEspera = 1 To 15
        If Not EstaEscuchando(p) Then Exit For
        WScript.Sleep 1000
    Next
End Sub

' ============================================================
' PARSEO DE LA SALIDA DE netstat -ano. Todo lo que sigue esta MEDIDO con
' cscript sobre el netstat de esta PC: simularlo en otro lenguaje no alcanza
' (str.split() de Python colapsa espacios y Split() de VBScript NO).
'
' La linea real es
'   '  TCP    127.0.0.1:5000         0.0.0.0:0              LISTENING       27800'
' y Split() da UBound=36 con la mayoria de los elementos VACIOS. Los no
' vacios quedaron en los indices 2 (protocolo), 6 (direccion local), 15
' (direccion remota), 29 (estado) y 36 (PID). Los indices CAMBIAN con el ancho
' de la direccion, y los dos espacios del principio ya generan vacios: por eso
' NADA se lee por indice fijo.
'   - ANCLA: el token exactamente igual a "LISTENING".
'   - PID: el primer token no vacio DESPUES del ancla.
'   - DIRECCION LOCAL: el primer token con ':' ANTES del ancla que termina en
'     ':<puerto>'. No sirve "el primer no vacio hacia atras": ese es la
'     direccion REMOTA (0.0.0.0:0), que no termina en el puerto.
'
' La version anterior leia partes(1) y partes(4) por indice fijo y devolvia
' SIEMPRE "": con la bandera el .vbs no cerraba nada, no arrancaba y abria el
' navegador sobre la app vieja (bloqueante B1 del review del 23/09/2026).
'
' SUPUESTOS (declarados, no defendidos):
'   1. El token de estado es la palabra INGLESA "LISTENING". Es una asuncion
'      PRE-EXISTENTE y SISTEMICA: la comparten modules/shared/relanzar_app.py
'      (filtra por LISTENING en la salida de netstat) e iniciar.bat (find
'      "LISTENING"). Medido en esta PC (Windows en espanol): la cabecera del
'      listado esta localizada ("Conexiones activas") pero los estados siguen en
'      ingles (21 LISTENING / 61 ESTABLISHED / 106 TIME_WAIT), asi que se
'      sostiene. Un netstat con los estados traducidos romperia los tres
'      mecanismos a la vez; aca el fallo seria fail-safe (sin el token no se
'      cierra nada y el usuario queda donde estaba), pero EstaEscuchando
'      diria "no escucha" y el .vbs arrancaria una segunda instancia.
'   2. La direccion local es la columna con ':' que termina en ':puerto' ANTES
'      del estado. Borde teorico: una linea LISTENING con el puerto SOLO en la
'      columna remota haria que se tome esa direccion y se devuelva el PID de esa
'      conexion. Con el netstat real no puede pasar (en LISTENING la remota es
'      0.0.0.0:0 o [::]:0) y por eso no se defiende.
'   3. Los PID no se deduplican: un mismo proceso escuchando IPv4 e IPv6 aparece
'      dos veces y el llamador le hace taskkill dos veces (inofensivo: el
'      segundo no encuentra el proceso).
' ============================================================
' Indice del token exactamente igual a ancla (-1 si no esta).
' Se recorre con Do While + Exit Function por SIMPLICIDAD: no hace falta
' cortar solo el bucle sino salir de la funcion, y asi no hay dos formas de
' salir. (Exit For es semantica estandar de VBScript y el propio archivo lo
' usa en el bucle de espera del paso 3: la eleccion aca es de estilo, no una
' limitacion del lenguaje.)
Function IndiceDe(partes, ancla)
    Dim i
    IndiceDe = -1
    i = 0
    Do While i <= UBound(partes)
        If partes(i) = ancla Then
            IndiceDe = i
            Exit Function
        End If
        i = i + 1
    Loop
End Function

' Primer token no vacio de partes al ir desde desde en paso (+1/-1).
' Devuelve "" si no hay ninguno.
Function TokenVecino(partes, desde, paso)
    Dim k
    TokenVecino = ""
    k = desde
    Do While k >= 0 And k <= UBound(partes)
        If Len(partes(k)) > 0 Then
            TokenVecino = partes(k)
            Exit Function
        End If
        k = k + paso
    Loop
End Function

' Direccion local del puerto p: el primer token con ':' que, yendo hacia atras
' desde desde, termina en ':<puerto>'. La direccion remota no coincide (su
' puerto es el del otro extremo), asi que no hace falta distinguirla.
Function DireccionLocal(partes, desde, p)
    Dim k, v, sufijo
    DireccionLocal = ""
    sufijo = ":" & p
    k = desde
    Do While k >= 0
        v = partes(k)
        If InStr(v, ":") > 0 Then
            If Right(v, Len(sufijo)) = sufijo Then
                DireccionLocal = v
                Exit Function
            End If
        End If
        k = k - 1
    Loop
End Function

Function PidsEscuchando(p)
    Dim ejec, partes, ancla, direccion, pid
    PidsEscuchando = ""
    On Error Resume Next
    Set ejec = objShell.Exec("cmd /c netstat -ano -p TCP")
    If Err.Number <> 0 Then
        Err.Clear
        On Error Goto 0
        Exit Function
    End If
    Do While Not ejec.StdOut.AtEndOfStream
        partes = Split(ejec.StdOut.ReadLine)
        ' El ancla es el ESTADO ("LISTENING"): los elementos vacios que genera
        ' Split no coinciden, asi que no importa cuantos espacios haya metido
        ' netstat (ni los dos del principio de la linea).
        ancla = IndiceDe(partes, "LISTENING")
        If ancla > 0 Then
            ' Direccion local (127.0.0.1:5000 o [::]:5000): la remota no sirve.
            direccion = DireccionLocal(partes, ancla - 1, p)
            If direccion <> "" Then
             If EsPuerto(direccion, p) Then
                ' Hacia adelante, el primer token con texto es el PID.
                pid = TokenVecino(partes, ancla + 1, 1)
                If EsNumero(pid) Then
                    If PidsEscuchando <> "" Then PidsEscuchando = PidsEscuchando & ";"
                    PidsEscuchando = PidsEscuchando & pid
                End If
             End If
            End If
        End If
    Loop
    On Error Goto 0
End Function

' ============================================================
' Primer PID que escucha el puerto ("" si no hay ninguno). Se conserva porque
' es comodo para diagnostico; el cierre de procesos usa PidsEscuchando (todos).
' ============================================================
Function PidEscuchando(p)
    Dim lista
    PidEscuchando = ""
    lista = PidsEscuchando(p)
    If InStr(lista, ";") > 0 Then
        PidEscuchando = Left(lista, InStr(lista, ";") - 1)
    Else
        PidEscuchando = lista
    End If
End Function

' ============================================================
' ¿El texto es un entero positivo? (guarda contra lineas con otro formato).
' ============================================================
Function EsNumero(texto)
    Dim i, c
    EsNumero = False
    If Len(texto) = 0 Then Exit Function
    For i = 1 To Len(texto)
        c = Mid(texto, i, 1)
        If c < "0" Or c > "9" Then Exit Function
    Next
    EsNumero = True
End Function

' ============================================================
' ¿La direccion local '127.0.0.1:5000' o '[::]:5000' es del puerto p?
' El ':' de adelante evita confundir 5000 con 15000.
' ============================================================
Function EsPuerto(direccion, p)
    Dim k, d
    EsPuerto = False
    d = Trim(direccion)
    k = ":" & p
    If Len(d) >= Len(k) Then
        If Right(d, Len(k)) = k Then EsPuerto = True
    End If
End Function

' ============================================================
' ¿Hay algo escuchando en el puerto? Se usa netstat (disponible en cualquier
' Windows) para no depender de WMI.
' ============================================================
Function EstaEscuchando(p)
    ' Se apoya en PidsEscuchando: el parseo de netstat -ano vive en UN solo
    ' lugar (el mismo que usa el cierre por bandera), asi no pueden divergir.
    EstaEscuchando = (PidsEscuchando(p) <> "")
End Function
