#!/usr/bin/env bash

# pass version number as an argument 

echo $1 > version.txt
pip install -e ..
pip install -r requirements.txt
rm -rf build/ dist/ release/
rm *.dmg
pyinstaller specter_desktop.spec --osx-bundle-identifier 'solutions.specter.desktop'
pyinstaller specterd.spec

if [[ "$2" != '' ]]
then
    echo 'Attempting to code sign...'
    python3 fix_app_qt_folder_names_for_codesign.py dist/Specter.app
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQml/Models.2/libmodelsplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQml/Models.2/libmodelsplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQml/WorkerScript.2/libworkerscriptplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQml/WorkerScript.2/libworkerscriptplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick.2/libqtquick2plugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick.2/libqtquick2plugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Particles.2/libparticlesplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Particles.2/libparticlesplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Templates.2/libqtquicktemplates2plugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Templates.2/libqtquicktemplates2plugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Controls.2/libqtquickcontrols2plugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Controls.2/libqtquickcontrols2plugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Controls.2/Fusion/libqtquickcontrols2fusionstyleplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Controls.2/Fusion/libqtquickcontrols2fusionstyleplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Controls.2/Universal/libqtquickcontrols2universalstyleplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Controls.2/Universal/libqtquickcontrols2universalstyleplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Controls.2/Material/libqtquickcontrols2materialstyleplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Controls.2/Material/libqtquickcontrols2materialstyleplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Controls.2/Imagine/libqtquickcontrols2imaginestyleplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Controls.2/Imagine/libqtquickcontrols2imaginestyleplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Window.2/libwindowplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/qml/QtQuick/Window.2/libwindowplugin.dylib"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuickControls2.framework/Versions/5/QtQuickControls2"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuickControls2.framework/Versions/5/QtQuickControls2"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuickParticles.framework/Versions/5/QtQuickParticles"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuickParticles.framework/Versions/5/QtQuickParticles"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtRemoteObjects.framework/Versions/5/QtRemoteObjects"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtRemoteObjects.framework/Versions/5/QtRemoteObjects"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtNetworkAuth.framework/Versions/5/QtNetworkAuth"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtNetworkAuth.framework/Versions/5/QtNetworkAuth"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWebEngineCore.framework/Versions/5/QtWebEngineCore"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWebEngineCore.framework/Versions/5/QtWebEngineCore"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWebEngineCore.framework/Helpers/QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWebEngineCore.framework/Helpers/QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWebEngineCore.framework/Helpers/QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuick3DRender.framework/Versions/5/QtQuick3DRender"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuick3DRender.framework/Versions/5/QtQuick3DRender"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtDesigner.framework/Versions/5/QtDesigner"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtDesigner.framework/Versions/5/QtDesigner"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtNfc.framework/Versions/5/QtNfc"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtNfc.framework/Versions/5/QtNfc"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuick3DAssetImport.framework/Versions/5/QtQuick3DAssetImport"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuick3DAssetImport.framework/Versions/5/QtQuick3DAssetImport"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWebEngineWidgets.framework/Versions/5/QtWebEngineWidgets"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWebEngineWidgets.framework/Versions/5/QtWebEngineWidgets"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuickWidgets.framework/Versions/5/QtQuickWidgets"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuickWidgets.framework/Versions/5/QtQuickWidgets"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuick3DRuntimeRender.framework/Versions/5/QtQuick3DRuntimeRender"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuick3DRuntimeRender.framework/Versions/5/QtQuick3DRuntimeRender"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtHelp.framework/Versions/5/QtHelp"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtHelp.framework/Versions/5/QtHelp"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtPrintSupport.framework/Versions/5/QtPrintSupport"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtPrintSupport.framework/Versions/5/QtPrintSupport"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtGui.framework/Versions/5/QtGui"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtGui.framework/Versions/5/QtGui"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtDBus.framework/Versions/5/QtDBus"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtDBus.framework/Versions/5/QtDBus"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWebSockets.framework/Versions/5/QtWebSockets"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWebSockets.framework/Versions/5/QtWebSockets"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuick3DUtils.framework/Versions/5/QtQuick3DUtils"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuick3DUtils.framework/Versions/5/QtQuick3DUtils"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuickTemplates2.framework/Versions/5/QtQuickTemplates2"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuickTemplates2.framework/Versions/5/QtQuickTemplates2"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtPositioningQuick.framework/Versions/5/QtPositioningQuick"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtPositioningQuick.framework/Versions/5/QtPositioningQuick"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtLocation.framework/Versions/5/QtLocation"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtLocation.framework/Versions/5/QtLocation"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtXml.framework/Versions/5/QtXml"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtXml.framework/Versions/5/QtXml"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtSerialPort.framework/Versions/5/QtSerialPort"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtSerialPort.framework/Versions/5/QtSerialPort"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuick.framework/Versions/5/QtQuick"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuick.framework/Versions/5/QtQuick"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtCore.framework/Versions/5/QtCore"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtCore.framework/Versions/5/QtCore"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQml.framework/Versions/5/QtQml"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQml.framework/Versions/5/QtQml"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWebChannel.framework/Versions/5/QtWebChannel"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWebChannel.framework/Versions/5/QtWebChannel"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtMultimedia.framework/Versions/5/QtMultimedia"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtMultimedia.framework/Versions/5/QtMultimedia"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQmlWorkerScript.framework/Versions/5/QtQmlWorkerScript"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQmlWorkerScript.framework/Versions/5/QtQmlWorkerScript"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtOpenGL.framework/Versions/5/QtOpenGL"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtOpenGL.framework/Versions/5/QtOpenGL"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWebEngine.framework/Versions/5/QtWebEngine"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWebEngine.framework/Versions/5/QtWebEngine"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtMacExtras.framework/Versions/5/QtMacExtras"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtMacExtras.framework/Versions/5/QtMacExtras"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtTest.framework/Versions/5/QtTest"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtTest.framework/Versions/5/QtTest"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWidgets.framework/Versions/5/QtWidgets"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtWidgets.framework/Versions/5/QtWidgets"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtPositioning.framework/Versions/5/QtPositioning"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtPositioning.framework/Versions/5/QtPositioning"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtBluetooth.framework/Versions/5/QtBluetooth"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtBluetooth.framework/Versions/5/QtBluetooth"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuick3D.framework/Versions/5/QtQuick3D"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuick3D.framework/Versions/5/QtQuick3D"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuickShapes.framework/Versions/5/QtQuickShapes"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuickShapes.framework/Versions/5/QtQuickShapes"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuickTest.framework/Versions/5/QtQuickTest"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQuickTest.framework/Versions/5/QtQuickTest"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtNetwork.framework/Versions/5/QtNetwork"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtNetwork.framework/Versions/5/QtNetwork"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtXmlPatterns.framework/Versions/5/QtXmlPatterns"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtXmlPatterns.framework/Versions/5/QtXmlPatterns"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtSvg.framework/Versions/5/QtSvg"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtSvg.framework/Versions/5/QtSvg"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtMultimediaWidgets.framework/Versions/5/QtMultimediaWidgets"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtMultimediaWidgets.framework/Versions/5/QtMultimediaWidgets"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQmlModels.framework/Versions/5/QtQmlModels"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtQmlModels.framework/Versions/5/QtQmlModels"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtSensors.framework/Versions/5/QtSensors"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtSensors.framework/Versions/5/QtSensors"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtTextToSpeech.framework/Versions/5/QtTextToSpeech"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtTextToSpeech.framework/Versions/5/QtTextToSpeech"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtSql.framework/Versions/5/QtSql"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtSql.framework/Versions/5/QtSql"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtConcurrent.framework/Versions/5/QtConcurrent"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app/Contents/Resources/PyQt5/Qt/lib/QtConcurrent.framework/Versions/5/QtConcurrent"
    codesign -fs "$2" --deep --force --verbose -o runtime --entitlements entitlements.plist --preserve-metadata=identifier,entitlements,requirements,runtime --timestamp "dist/Specter.app"
    ditto -c -k --keepParent "dist/Specter.app" dist/Specter.zip
    xcrun altool --notarize-app -t osx -f dist/Specter.zip --primary-bundle-id "solutions.specter.desktop" -u "$3" --password "@keychain:AC_PASSWORD"
    sleep 900
    xcrun stapler staple "dist/Specter.app"
fi

mkdir release

create-dmg 'dist/Specter.app'
mv "Specter 0.0.0.dmg" release/SpecterDesktop-$1.dmg
zip release/specterd-$1-osx.zip dist/specterd