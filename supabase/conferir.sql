-- Consulta de estrutura e evidências; não altera os dados.
select column_name, data_type, is_nullable, column_default
from information_schema.columns
where table_schema = 'public' and table_name = 'readings'
order by ordinal_position;

select relrowsecurity as rls_habilitado
from pg_class where oid = 'public.readings'::regclass;

select grantee, privilege_type
from information_schema.role_table_grants
where table_schema = 'public' and table_name = 'readings'
  and grantee in ('anon', 'authenticated')
order by grantee, privilege_type;

select device_id, message_id, level_percent, distance_cm, alert, received_at
from public.readings where device_id = 'g01'
order by received_at desc limit 50;
