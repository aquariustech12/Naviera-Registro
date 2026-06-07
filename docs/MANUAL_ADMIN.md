# Manual de uso del Administrador

Guia operativa para la persona encargada de administrar navieras, buques, documentos y entregables desde el panel de Django Admin de Naviera-Registro.

## Acceso

1. Abra la URL del administrador: `/admin/`.
2. Inicie sesion con el usuario administrativo asignado.
3. Verifique que se muestre el panel con las secciones principales del sistema.

Si no puede entrar, confirme que el usuario tenga permisos de `staff` y que la contrasena sea correcta.

## Secciones principales

### Navieras

Use esta seccion para consultar o actualizar empresas registradas.

Campos importantes:

- `nombre_empresa`: nombre de la naviera.
- `contacto_principal`: persona de contacto.
- `correo_electronico`: correo donde llegan avisos y entregables.
- `alta_completa`: indica si la naviera ya completo los documentos administrativos.
- `fecha_alta_completa`: fecha en que el sistema marco el alta como completada.

Dentro de una naviera tambien puede ver o agregar buques desde la tabla en linea.

### Buques

Use esta seccion para consultar los buques registrados por cada naviera.

Campos importantes:

- `nombre_buque`: nombre del buque.
- `OMI`: numero OMI del buque.
- `naviera`: empresa propietaria o solicitante.
- `metodo_pago`: esquema comercial, `100%` o `50% - 50%`.
- `pago_1_completado` y `pago_2_completado`: estado interno de pagos.

Evite cambiar estados de pago manualmente si no tiene confirmacion del comprobante correspondiente.

### Requisitos de buque

Use esta seccion para revisar documentos cargados por los clientes.

Categorias:

- `COTIZACION`: formulario de cotizacion del buque.
- `DOCUMENTAL`: documentos de verificacion PBIP por buque.
- `ADMINISTRATIVO`: documentos generales de alta de la naviera.

Acciones comunes:

1. Filtrar por categoria, naviera o fecha de subida.
2. Buscar por nombre de documento, naviera o buque.
3. Abrir el registro para revisar el archivo cargado.
4. Si el documento no cumple, capturar el motivo de rechazo antes de eliminarlo.

Importante: al eliminar un documento, el sistema puede enviar alerta por MIA y correo al cliente indicando que el documento fue rechazado. El motivo debe ser claro y util.

Ejemplos de motivos correctos:

- `El archivo no corresponde al documento solicitado.`
- `El documento esta vencido.`
- `La imagen no es legible. Favor de cargar una version clara en PDF.`
- `El documento pertenece a otra empresa o buque.`

Evite motivos ambiguos como `mal`, `incorrecto` o `revisar`.

### Documentos entregables

Use esta seccion para cargar documentos finales que el cliente podra descargar desde su portal.

Tipos disponibles:

- `COTIZACION`: propuesta economica o cotizacion.
- `INFORME_PBIP`: informe PBIP terminado.
- `FACTURA`: factura.
- `COMPROBANTE_PAGO`: comprobante de pago registrado.

Campos importantes:

- `naviera`: empresa que recibira el documento.
- `buque`: seleccione el buque cuando el documento pertenezca a un buque especifico.
- `tipo`: tipo de entregable.
- `archivo`: archivo principal, normalmente PDF.
- `archivo_xml`: XML opcional, usado principalmente para factura.
- `secuencia`: numero usado para diferenciar entregables del mismo tipo cuando aplique.

Importante: al crear un nuevo entregable, el sistema envia un correo automatico al cliente avisando que hay un documento disponible. Revise bien naviera, buque, tipo y archivo antes de guardar.

## Flujo diario recomendado

1. Entrar a `/admin/`.
2. Revisar `Navieras` nuevas y confirmar datos de contacto.
3. Revisar `Buques` nuevos y validar nombre/OMI.
4. Entrar a `Requisitos de buque` y filtrar documentos recientes.
5. Revisar documentos administrativos y PBIP cargados por los clientes.
6. Si un documento no cumple, escribir motivo de rechazo y eliminarlo para notificar al cliente.
7. Cuando el area correspondiente genere cotizaciones, facturas o informes, subirlos en `Documentos entregables`.
8. Confirmar que el cliente pueda ver el entregable desde el portal.

## Carga de cotizacion

1. Entrar a `Documentos entregables`.
2. Seleccionar `Agregar documento entregable`.
3. Elegir la `naviera`.
4. Elegir el `buque` correspondiente.
5. En `tipo`, seleccionar `COTIZACION`.
6. Adjuntar el archivo PDF en `archivo`.
7. Guardar.

El cliente vera la propuesta economica dentro del expediente del buque.

## Carga de informe PBIP

1. Entrar a `Documentos entregables`.
2. Seleccionar `Agregar documento entregable`.
3. Elegir la `naviera` y el `buque` auditado.
4. En `tipo`, seleccionar `INFORME_PBIP`.
5. Adjuntar el informe en PDF.
6. Guardar.

El portal marcara el buque como `Auditoria Completada` y permitira descargar el informe.

## Carga de factura PDF y XML

1. Entrar a `Documentos entregables`.
2. Seleccionar `Agregar documento entregable`.
3. Elegir la `naviera`.
4. Dejar `buque` vacio si la factura es general de la naviera.
5. En `tipo`, seleccionar `FACTURA`.
6. Adjuntar el PDF en `archivo`.
7. Adjuntar el XML en `archivo_xml`, si esta disponible.
8. Guardar.

El cliente vera botones separados para descargar PDF y XML cuando ambos existan.

## Rechazo de documentos

Use esta funcion cuando el cliente subio un archivo equivocado, vencido, ilegible o incompleto.

Procedimiento recomendado:

1. Entrar a `Requisitos de buque`.
2. Buscar el documento por naviera, buque o nombre.
3. Abrir el registro.
4. Escribir un motivo claro en `motivo_rechazo`.
5. Guardar si es necesario.
6. Eliminar el documento desde el admin.
7. Confirmar que aparezca el mensaje de eliminacion.

El cliente recibira correo indicando el motivo y podra volver a cargar el documento desde el portal.

## Buenas practicas

- Verifique dos veces la naviera antes de cargar un entregable.
- Use nombres de archivos claros: `Cotizacion_BuqueNombre.pdf`, `Factura_Naviera_Mes.pdf`, `InformePBIP_BuqueNombre.pdf`.
- No elimine documentos sin motivo de rechazo.
- No modifique pagos manualmente sin evidencia.
- No cambie `alta_completa` salvo que sepa exactamente por que lo hace.
- No cree usuarios desde el admin para clientes si el flujo normal de registro publico esta disponible.
- Si un cliente reporta que no ve un archivo, revise que el entregable tenga naviera correcta y, si aplica, buque correcto.

## Problemas frecuentes

### El cliente no ve una cotizacion

Revise que el entregable tenga:

- `tipo = COTIZACION`.
- La naviera correcta.
- El buque correcto.
- Archivo cargado en `archivo`.

### El cliente no ve una factura

Revise que exista un entregable con:

- `tipo = FACTURA`.
- La naviera correcta.
- Archivo PDF en `archivo`.
- XML en `archivo_xml`, si corresponde.

### El cliente dice que subio un documento pero aparece pendiente

Revise en `Requisitos de buque` si el documento se guardo con el nombre esperado. Si se rechazo y elimino, el cliente debe volver a cargarlo.

### Se cargo un entregable en la naviera equivocada

No lo deje publicado. Elimine el entregable incorrecto y vuelva a cargarlo con la naviera correcta.

## Contacto interno

Si hay duda sobre si un documento cumple, no lo apruebe por intuicion. Escale la revision al responsable tecnico o auditor antes de rechazar o continuar el expediente.
