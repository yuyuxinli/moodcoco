# Expert Eval Release Checklist

每次导出专家评测包前，至少确认以下事项：

1. 运行 `python expert-eval/runner.py --self-check` 通过
2. 运行 `python expert-eval/runner.py --route-replay` 生成最新 replay v2
3. `bundle.json`、`AGENTS.md`、`AUTO_EVAL_CHECKLIST.md` 与 `skills/*` 已同步
4. `expert-eval/cases/built_in_cases.json` 中的 case 与当前路由规则一致
5. 没有把 `know-myself`、`see-pattern`、`relationship-coach`、`scene-router` 混入首版 bundle
6. `scripts/build_expert_eval_pack.py` 可在当前 bundle 上成功导出
7. `start_expert_eval.command` 与 `start_expert_eval.bat` 已包含在打包结果中
8. manifest 中写明版本号、生成时间、评测范围与已知限制
9. 打包结果同时包含 bundle 本体、cases、runner、最新 replay 结果、启动脚本与说明文档
