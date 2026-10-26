{#- Custom generic test: the declared grain really is unique (no dbt_utils dependency). -#}
{% test unique_combination(model, combination) %}
select {{ combination | join(', ') }}, count(*) as rows_per_grain
from {{ model }}
group by {{ combination | join(', ') }}
having count(*) > 1
{% endtest %}
