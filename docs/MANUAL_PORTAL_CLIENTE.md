# Manual de uso del Portal del Cliente

Guia para clientes de Naviera-Registro. Este portal se usa para registrar buques, cargar documentos, consultar entregables y subir comprobantes de pago relacionados con el proceso PBIP.

## Acceso al portal

1. Abra la pagina principal del sistema.
2. Si aun no tiene cuenta, complete el formulario de `Registro de Navieras`.
3. Si ya tiene cuenta, vaya a la seccion `Usuarios registrados favor de acceder`.
4. Ingrese su nombre de usuario y contrasena.
5. Presione `Iniciar sesion`.

El nombre de usuario normalmente es el nombre de la empresa registrado.

## Registro de una naviera

Para registrarse por primera vez:

1. Escriba el `Nombre de la empresa`.
2. Escriba el `Contacto principal`.
3. Escriba el `Correo electronico`.
4. Acepte la Politica de Privacidad.
5. Presione `Registrar`.

Despues del registro, recibira por correo una contrasena temporal. Revise tambien la carpeta de spam o correo no deseado.

## Primer ingreso y cambio de contrasena

Por seguridad, el primer ingreso requiere cambiar la contrasena temporal.

1. Inicie sesion con el usuario y contrasena temporal recibidos por correo.
2. El sistema mostrara la pantalla `Actualizacion de Seguridad`.
3. Escriba la contrasena temporal actual.
4. Escriba una nueva contrasena.
5. Confirme la nueva contrasena.
6. Presione `Guardar Nueva Contrasena e Ingresar`.

A partir de ese momento use la nueva contrasena para entrar.

## Pantalla principal del portal

Al entrar vera las siguientes areas:

- `Gestion de Flota (PBIP)`: registro de buques y expedientes documentales.
- `Expediente de Alta de Cliente y Contrato`: documentos administrativos de la naviera.
- `Documentos Finales`: informes, facturas y documentos disponibles para descarga.
- `Comprobante de Pago por Buque`: carga de comprobantes segun el esquema de pago.

Use el boton `Cerrar Sesion` cuando termine.

## Registrar un buque

1. En `Gestion de Flota (PBIP)`, escriba el `Nombre del Buque`.
2. Escriba el `Numero OMI`.
3. Seleccione el metodo de pago:
   - `Pago 100%`.
   - `Pago 50% - 50%`.
4. Presione `Agregar Buque`.

El buque aparecera en la tabla `Buques Registrados`.

## Ver expediente de un buque

1. Localice el buque en `Buques Registrados`.
2. Presione `Ver Expediente`.
3. Se abrira el expediente pre-servicio del buque.

Dentro del expediente podra actualizar condiciones comerciales, descargar/subir formulario de cotizacion y cargar documentos PBIP.

## Actualizar metodo de pago

1. Abra `Ver Expediente` del buque.
2. Busque `Condicion Comercial / Metodo de Pago`.
3. Seleccione `Pago 100%` o `Pago 50% - 50%`.
4. Presione `Actualizar Condiciones`.

Realice este cambio solo si el acuerdo comercial cambio antes de cargar comprobantes de pago.

## Formulario de cotizacion

1. Abra el expediente del buque.
2. En la seccion `COTIZACION`, presione `Descargar` para obtener el formulario FGMP-FC-01.
3. Complete el formulario.
4. Seleccione el archivo PDF terminado.
5. Presione `Subir`.

Cuando el archivo se cargue correctamente, el estado cambiara a `Cargado`.

Cuando Global Maritime Protection cargue la propuesta economica, aparecera el aviso `Propuesta Economica OPR lista` con el boton `Descargar Propuesta`.

## Checklist documental PBIP

1. Abra el expediente del buque.
2. En `LISTA DE VERIFICACION DOCUMENTAL (FGMP-RD-01)`, presione `Abrir Checklist Documental`.
3. Revise los puntos documentales del listado.
4. En cada punto, seleccione el archivo correspondiente.
5. Presione `Subir`.
6. Verifique que el estado cambie de `Pendiente` a `Cargado`.

Cada documento debe cargarse en el punto que corresponde. Si sube un documento equivocado, el area administrativa puede rechazarlo y recibira aviso por correo.

## Expediente administrativo de alta

En `Expediente de Alta de Cliente y Contrato`, cargue los documentos generales de la naviera:

- Acta Constitutiva.
- Poder Notarial.
- INE Representante.
- Opinion SAT.
- Estado de Cuenta.
- Directorio Contactos.

Para cada documento:

1. Localice el nombre del documento.
2. Seleccione el archivo.
3. Presione `Subir`.
4. Verifique que aparezca la etiqueta `Cargado`.

Cuando todos los documentos administrativos requeridos esten recibidos, el portal mostrara `ALTA COMPLETADA`.

## Documentos finales

En la seccion `Documentos Finales` podra descargar archivos liberados por Global Maritime Protection.

### Informes de auditoria PBIP

Cuando un informe este disponible:

1. Busque el nombre del buque.
2. Presione `Descargar`.

Si no aparece el informe, aun no ha sido cargado por el area correspondiente.

### Facturacion

Cuando la factura este disponible, vera botones para:

- `Descargar PDF`.
- `Descargar XML`, si el XML fue cargado.

Si aparece el mensaje `Su factura aun no esta disponible`, espere la liberacion administrativa.

## Comprobantes de pago

Los comprobantes se cargan por buque.

### Pago 100%

1. Busque el buque en `Comprobante de Pago por Buque`.
2. Seleccione el archivo del comprobante en PDF, JPG o PNG.
3. Presione `Subir`.
4. Cuando se procese, el portal marcara el pago como completado.

### Pago 50% - 50%

Primero debe subir el anticipo:

1. Seleccione el archivo del primer 50%.
2. Presione `Subir Anticipo`.

Cuando el primer pago este verificado, el portal permitira subir el finiquito:

1. Seleccione el archivo del segundo 50%.
2. Presione `Subir Finiquito`.

Cuando ambos esten completos, el portal mostrara que la liquidacion total fue completada.

## Recomendaciones para cargar archivos

- Use archivos legibles y completos.
- Prefiera PDF para documentos oficiales.
- Para comprobantes de pago tambien se aceptan JPG o PNG.
- Evite fotografias borrosas, recortadas o con sombras.
- Cargue cada archivo en el apartado correcto.
- No suba el mismo comprobante varias veces; el sistema puede detectarlo como duplicado.
- Use nombres de archivo claros, por ejemplo `Acta_Naviera.pdf` o `Comprobante_Buque_OMI.pdf`.

## Mensajes y estados

- `Pendiente`: el documento aun no se ha cargado.
- `Cargado`: el documento fue recibido por el sistema.
- `Auditoria Completada`: el informe PBIP ya fue cargado para ese buque.
- `ALTA COMPLETADA`: los documentos administrativos de la naviera ya fueron recibidos.

## Si un documento fue rechazado

Si recibe un correo indicando que un documento fue rechazado:

1. Lea el motivo del rechazo.
2. Entre al portal.
3. Vaya a la seccion donde habia cargado el documento.
4. Seleccione el archivo corregido.
5. Presione `Subir` nuevamente.

Si tiene duda sobre el motivo, responda al correo de notificacion o contacte al equipo de operaciones.

## Problemas frecuentes

### No recibi la contrasena temporal

Revise spam o correo no deseado. Confirme que el correo registrado sea correcto.

### No puedo iniciar sesion

Verifique que este usando el nombre de usuario de la empresa y la contrasena correcta. Si ya cambio la contrasena temporal, use la nueva.

### Subi un archivo pero sigue pendiente

Actualice la pagina. Si sigue pendiente, confirme que cargo el archivo en el apartado correcto.

### No veo mi factura o informe

Los documentos finales aparecen cuando Global Maritime Protection los carga al expediente. Si no aparecen, aun no estan disponibles.

### El sistema no acepta mi comprobante

Confirme que el archivo sea PDF, JPG o PNG y que no sea el mismo comprobante cargado anteriormente.

## Cierre de sesion

Al terminar, presione `Cerrar Sesion` en la parte superior del portal, especialmente si usa una computadora compartida.
