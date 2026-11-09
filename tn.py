nums = [8, 1, 2, 2, 3]
res = []
for i in range(len(nums)):
    c = 0
    for j in range(len(nums)):
        if nums[i] > nums[j] and nums[i] != nums[j]:
            c += 1
    res.append(c)
print(res)