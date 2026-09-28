export function mailPolicyRules(policy) {
  return {
    to_group_ids: [{
      type: 'array', required: !policy.cc_group_ids?.length,
      validator: (_rule, value, callback) => callback(
        value?.length || policy.cc_group_ids?.length ? undefined : new Error('请至少选择一个默认主送组或抄送组'),
      ), trigger: 'change',
    }],
  }
}
