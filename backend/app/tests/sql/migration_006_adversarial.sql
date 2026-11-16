-- C-08 1.4: inserciones adversas contra PostgreSQL real tras aplicar la migración 006.
-- Prerrequisito: esquema 001-005 + 006 aplicado (o stubs usuario/turno/pago/evento_pago). Cada sentencia
-- marcada ERR debe fallar y las OK deben pasar. Ver evidencia en el reporte del apply.
\set ON_ERROR_STOP 0
insert into usuario(id) values ('00000000-0000-0000-0000-000000000001');
insert into turno(id) values ('00000000-0000-0000-0000-0000000000a1');
insert into pago(id,monto) values ('00000000-0000-0000-0000-0000000000b1',10000);
\echo '== OK esperado: devolucion 60% valida'
insert into devolucion(id,pago_id,turno_id,monto,porcentaje,idempotency_key) values ('00000000-0000-0000-0000-0000000000c1','00000000-0000-0000-0000-0000000000b1','00000000-0000-0000-0000-0000000000a1',6000,60,'dev_b1');
\echo '== ERR: segunda devolucion por pago'
insert into devolucion(pago_id,turno_id,monto,porcentaje,idempotency_key) values ('00000000-0000-0000-0000-0000000000b1','00000000-0000-0000-0000-0000000000a1',6000,60,'dev_b1x');
insert into pago(id,monto) values ('00000000-0000-0000-0000-0000000000b2',10000);
\echo '== ERR: porcentaje 0'
insert into devolucion(pago_id,turno_id,monto,porcentaje,idempotency_key) values ('00000000-0000-0000-0000-0000000000b2','00000000-0000-0000-0000-0000000000a1',1,0,'k0');
\echo '== ERR: porcentaje 50'
insert into devolucion(pago_id,turno_id,monto,porcentaje,idempotency_key) values ('00000000-0000-0000-0000-0000000000b2','00000000-0000-0000-0000-0000000000a1',5000,50,'k50');
\echo '== ERR: monto 0'
insert into devolucion(pago_id,turno_id,monto,porcentaje,idempotency_key) values ('00000000-0000-0000-0000-0000000000b2','00000000-0000-0000-0000-0000000000a1',0,60,'km0');
\echo '== ERR: monto negativo'
insert into devolucion(pago_id,turno_id,monto,porcentaje,idempotency_key) values ('00000000-0000-0000-0000-0000000000b2','00000000-0000-0000-0000-0000000000a1',-5,60,'kneg');
\echo '== ERR: monto > pago (trigger)'
insert into devolucion(pago_id,turno_id,monto,porcentaje,idempotency_key) values ('00000000-0000-0000-0000-0000000000b2','00000000-0000-0000-0000-0000000000a1',10000.01,100,'kbig');
\echo '== ERR: ejecutada sin mp_refund_id'
update devolucion set estado='ejecutada' where id='00000000-0000-0000-0000-0000000000c1';
\echo '== ERR: pendiente->ejecutada (trigger, saltando aprobada)'
update devolucion set estado='ejecutada', mp_refund_id='r1', aprobada_por='00000000-0000-0000-0000-000000000001', aprobada_at=now(), ejecutada_por='00000000-0000-0000-0000-000000000001', ejecutada_at=now() where id='00000000-0000-0000-0000-0000000000c1';
\echo '== ERR: aprobada sin actor (CHECK)'
update devolucion set estado='aprobada' where id='00000000-0000-0000-0000-0000000000c1';
\echo '== OK: pendiente->aprobada con actor'
update devolucion set estado='aprobada', aprobada_por='00000000-0000-0000-0000-000000000001', aprobada_at=now() where id='00000000-0000-0000-0000-0000000000c1';
\echo '== OK: aprobada->ejecutada'
update devolucion set estado='ejecutada', mp_refund_id='r1', ejecutada_por='00000000-0000-0000-0000-000000000001', ejecutada_at=now() where id='00000000-0000-0000-0000-0000000000c1';
\echo '== ERR: ejecutada->pendiente (retroceso, trigger)'
update devolucion set estado='pendiente' where id='00000000-0000-0000-0000-0000000000c1';
\echo '== OK: evento devolucion_rechazada'
insert into evento_pago(pago_id,tipo_evento) values ('00000000-0000-0000-0000-0000000000b1','devolucion_rechazada');
\echo '== ERR: tipo evento invalido'
insert into evento_pago(pago_id,tipo_evento) values ('00000000-0000-0000-0000-0000000000b1','inventado');
\echo '== comprobantes'
insert into comprobante(pago_id,turno_id,concepto,monto,simulado) values ('00000000-0000-0000-0000-0000000000b1','00000000-0000-0000-0000-0000000000a1','pago',10000,true);
\echo '== ERR: segundo recibo de pago'
insert into comprobante(pago_id,turno_id,concepto,monto,simulado) values ('00000000-0000-0000-0000-0000000000b1','00000000-0000-0000-0000-0000000000a1','pago',10000,true);
\echo '== OK: recibo devolucion'
insert into comprobante(pago_id,devolucion_id,turno_id,concepto,monto,simulado) values ('00000000-0000-0000-0000-0000000000b1','00000000-0000-0000-0000-0000000000c1','00000000-0000-0000-0000-0000000000a1','devolucion',6000,true);
\echo '== ERR: concepto devolucion sin devolucion_id'
insert into comprobante(pago_id,turno_id,concepto,monto,simulado) values ('00000000-0000-0000-0000-0000000000b2','00000000-0000-0000-0000-0000000000a1','devolucion',1,true);
select numero, concepto from comprobante order by numero;
\echo '== app_turnos: UPDATE/DELETE comprobante denegado'
grant usage on schema public to app_turnos;
set role app_turnos;
update comprobante set monto=1;
delete from comprobante;
select has_table_privilege('app_turnos','comprobante','INSERT') ins, has_table_privilege('app_turnos','comprobante','UPDATE') upd, has_table_privilege('app_turnos','devolucion','DELETE') deldev;
